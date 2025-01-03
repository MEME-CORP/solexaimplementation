# src/telegram_bot/telegram_bot.py

import logging
import re
import os
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    Application,
    Defaults
)
from telegram import Update

# --- Import your modules (adjust imports to your project structure) ---
from src.config import Config
from src.ai_generator import AIGenerator
from src.memory_processor import MemoryProcessor
from src.memory_decision import select_relevant_memories
from src.story_circle_manager import (
    get_current_context,
    progress_narrative
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('TelegramBot')


class TelegramBot:
    def __init__(self):
        """Initialize the Telegram bot with basic configuration."""
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.generator = AIGenerator(mode='telegram')
        self.memory_processor = MemoryProcessor()
        self.user_conversations = {}
        self.MAX_MEMORY = Config.MAX_MEMORY

    def setup(self) -> Application:
        """
        Build the Application with job queue,
        add command handlers, message handlers, and background jobs.
        """
        try:
            # Create the Application, enabling the job queue
            defaults = Defaults(block=False)
            self.application = (
                ApplicationBuilder()
                .token(self.token)
                .defaults(defaults)
                .build()
            )

            # Register command/message handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("chatid", self.chatid_command))
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )

            # Check if job queue is available
            if self.application.job_queue:
                logger.info("Setting up job queue tasks...")

                try:
                    # ----------------------------------------------------------------
                    # 1) DEBUG JOB: REPEATS EVERY 60 SECONDS (after a 10-second delay)
                    # ----------------------------------------------------------------
                    self.application.job_queue.run_repeating(
                        callback=self.debug_memory_job,
                        interval=43200,   # run every 60 seconds
                        first=10       # wait 10 seconds before first run
                    )
                    logger.info("Debug repeating job scheduled: runs every 60s")

                    # ----------------------------------------------------------------
                    # 2) NARRATIVE JOB: EVERY 6 HOURS (unchanged)
                    # ----------------------------------------------------------------
                    self.application.job_queue.run_repeating(
                        callback=self.update_narrative_job,
                        interval=21600,  # 6 hours
                        first=15         # start 15 seconds after bot starts
                    )
                    logger.info("Narrative repeating job scheduled: runs every 6h")

                except Exception as e:
                    logger.error(f"Error setting up job queue tasks: {e}")
            else:
                logger.warning("Job queue not available. Background tasks will not run.")

            return self.application

        except Exception as e:
            logger.error(f"Error in setup: {e}")
            raise

    async def debug_memory_job(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Debug job that runs every 60 seconds to prove the job queue is working.
        We simulate a 'daily' memory job by printing logs and clearing conversation data.
        """
        try:
            logger.info("[DEBUG-JOB] Starting memory processing job...")
            logger.info(f"[DEBUG-JOB] Current user_conversations count: {len(self.user_conversations)}")

            if self.user_conversations:
                logger.info("[DEBUG-JOB] Processing user conversations...")
                try:
                    await self.memory_processor.process_daily_memories(self.user_conversations)
                    self.user_conversations.clear()
                    logger.info("[DEBUG-JOB] Memory processing completed successfully (debug)")
                except Exception as e:
                    logger.error(f"[DEBUG-JOB] Error processing daily memories: {e}")
            else:
                logger.info("[DEBUG-JOB] No conversations to process this cycle")

            # Show next run time for clarity
            if context.job and context.job.next_run_time:
                logger.info(f"[DEBUG-JOB] Next run scheduled for: {context.job.next_run_time.isoformat()}")

        except Exception as e:
            logger.error(f"[DEBUG-JOB] Critical error in memory job: {e}")
            logger.exception("[DEBUG-JOB] Full error details:")
        finally:
            logger.info("[DEBUG-JOB] Memory processing job cycle completed (debug)")

    async def update_narrative_job(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Job to update the story circle narrative every 6 hours.
        """
        try:
            logger.info("[NARRATIVE-JOB] Progressing story circle narrative...")
            result = progress_narrative()
            if result:
                logger.info("[NARRATIVE-JOB] Story circle progression completed")
            else:
                logger.warning("[NARRATIVE-JOB] No story circle progression needed or possible")
        except Exception as e:
            logger.error(f"[NARRATIVE-JOB] Error in story circle progression: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start command handler
        """
        await update.message.reply_text(
            f"Hello! I'm Fwogai bot. Mention me using @{Config.BOT_USERNAME}"
        )

    async def chatid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /chatid command handler
        """
        if not update.effective_chat:
            return
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Chat ID: {update.effective_chat.id}"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle any text message (that isn't a command).
        """
        if not update.message or not update.message.text:
            return

        user_message = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or f'User{user_id}'

        # Add user message to conversation history
        self.add_to_conversation_history(user_id, user_message, is_bot=False)

        try:
            # Generate AI response
            response = await self.generate_response(user_message, user_id, username)

            # Trim response if it's too long
            if len(response) > 200:
                truncated = response[:200]
                last_sentence = re.search(r'^.*[.!?]', truncated)
                if last_sentence:
                    response = last_sentence.group(0)
                else:
                    response = truncated[:truncated.rfind(' ')] + '...'

            # Send response
            await update.message.reply_text(response)

            # Add the bot's response to history
            self.add_to_conversation_history(user_id, response, is_bot=True)

        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            await update.message.reply_text(
                "Sorry, I encountered an error while processing your message."
            )

    def add_to_conversation_history(self, user_id, message, is_bot):
        """
        Save message in local conversation history for each user.
        """
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        self.user_conversations[user_id].append({
            'content': message,
            'is_bot': is_bot,
            'timestamp': asyncio.get_event_loop().time()
        })

        # Keep the last MAX_MEMORY messages
        if len(self.user_conversations[user_id]) > self.MAX_MEMORY:
            self.user_conversations[user_id].pop(0)

    def get_conversation_context(self, user_id):
        """
        Build a textual conversation context from the user's conversation history.
        """
        history = self.user_conversations.get(user_id, [])
        return '\n'.join([
            f"{'Assistant' if msg['is_bot'] else 'User'}: {msg['content']}"
            for msg in history
        ])

    async def generate_response(self, user_message, user_id, username):
        """
        Use your custom AI pipeline to generate a bot response.
        """
        try:
            # Gather conversation context
            conversation_context = self.get_conversation_context(user_id)
            # Pull relevant memories from DB or other source
            memories = select_relevant_memories(username, user_message)
            # Get story circle context
            narrative_context = get_current_context()
            # Random emotion format
            emotion_format = random.choice(self.generator.emotion_formats)['format']

            # Generate the AI content
            response = self.generator.generate_content(
                user_message=user_message,
                user_id=user_id,
                username=username,
                conversation_context=conversation_context,
                memories=memories,
                narrative_context=narrative_context,
                emotion_format=emotion_format
            )

            logger.info(f"Generated response (first 50 chars): {response[:50]}...")
            return response

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Sorry, I couldn't process your request at the moment."
