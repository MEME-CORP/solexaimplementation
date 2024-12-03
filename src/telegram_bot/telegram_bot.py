# src/telegram_bot/telegram_bot.py

import logging
import re
import json
import os
from pathlib import Path
from typing import Optional
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    ContextTypes, 
    filters, 
    Application,
    JobQueue,
    Defaults
)
from telegram import Update
from dotenv import load_dotenv
from src.ai_generator import AIGenerator
from src.config import Config
import asyncio
from src.memory_processor import MemoryProcessor
from src.memory_decision import select_relevant_memories
from src.story_circle_manager import get_current_context, update_story_circle, progress_narrative
from datetime import datetime, time

# Load environment variables and configure logging
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('TelegramBot')

class TelegramBot:
    def __init__(self):
        """Initialize bot with basic configuration."""
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.generator = AIGenerator(mode='telegram')
        self.memory_processor = MemoryProcessor()
        self.user_conversations = {}
        self.MAX_MEMORY = Config.MAX_MEMORY
        self._running = True

    def setup(self) -> Application:
        """Setup the application and handlers."""
        try:
            # Build application with job queue enabled
            defaults = Defaults(block=False)
            self.application = (
                ApplicationBuilder()
                .token(self.token)
                .defaults(defaults)
                .build()
            )
            
            # Add handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("chatid", self.chatid_command))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            # Only add background tasks if job queue is available
            if self.application.job_queue:
                logger.info("Setting up job queue tasks...")
                try:
                    self.application.job_queue.run_daily(
                        self.process_memories_job,
                        time=time(hour=23, minute=55)
                    )
                    self.application.job_queue.run_repeating(
                        self.update_narrative_job,
                        interval=21600,  # 6 hours in seconds
                        first=10  # Start first run after 10 seconds
                    )
                    logger.info("Job queue tasks set up successfully")
                except Exception as e:
                    logger.error(f"Error setting up job queue tasks: {e}")
            else:
                logger.warning("Job queue not available. Background tasks will not run.")
            
            return self.application

        except Exception as e:
            logger.error(f"Error in setup: {e}")
            raise

    async def process_memories_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job to process memories daily."""
        try:
            logger.info("Starting nightly memory processing...")
            if self.user_conversations:  # Only process if there are conversations
                await self.memory_processor.process_daily_memories(self.user_conversations)
                self.user_conversations.clear()
                logger.info("Nightly memory processing completed")
            else:
                logger.info("No conversations to process")
        except Exception as e:
            logger.error(f"Error in nightly memory processing: {e}")

    async def update_narrative_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job to update narrative every 6 hours."""
        try:
            logger.info("Progressing story circle narrative...")
            # Call the synchronous function
            result = progress_narrative()
            if result:
                logger.info("Story circle progression completed")
            else:
                logger.warning("No story circle progression needed or possible")
        except Exception as e:
            logger.error(f"Error in story circle progression: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for the /start command."""
        await update.message.reply_text(f"Hello! I'm Fwogai bot. Mention me using @{Config.BOT_USERNAME}")

    async def chatid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for the /chatid command."""
        if not update.effective_chat:
            return
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Chat ID: {update.effective_chat.id}"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages."""
        if not update.message or not update.message.text:
            return

        user_message = update.message.text
        user_id = update.message.from_user.id
        username = update.message.from_user.username or f'User{user_id}'

        # Add to conversation history
        self.add_to_conversation_history(user_id, user_message, is_bot=False)

        try:
            # Generate response
            response = await self.generate_response(user_message, user_id, username)

            # Trim content if needed
            if len(response) > 200:
                truncated = response[:200]
                last_sentence = re.search(r'^.*[.!?]', truncated)
                if last_sentence:
                    response = last_sentence.group(0)
                else:
                    response = truncated[:truncated.rfind(' ')] + '...'

            # Send response
            await update.message.reply_text(response)

            # Add bot response to conversation history
            self.add_to_conversation_history(user_id, response, is_bot=True)
            
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            await update.message.reply_text("Sorry, I encountered an error while processing your message.")

    def add_to_conversation_history(self, user_id, message, is_bot):
        """Add message to conversation history."""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        self.user_conversations[user_id].append({
            'content': message,
            'is_bot': is_bot,
            'timestamp': asyncio.get_event_loop().time()
        })
        # Keep only the last MAX_MEMORY messages
        if len(self.user_conversations[user_id]) > self.MAX_MEMORY:
            self.user_conversations[user_id].pop(0)

    def get_conversation_context(self, user_id):
        """Get conversation history for a user."""
        history = self.user_conversations.get(user_id, [])
        return '\n'.join([
            f"{'Assistant' if msg['is_bot'] else 'User'}: {msg['content']}"
            for msg in history
        ])

    async def generate_response(self, user_message, user_id, username):
        """Generate response using AI."""
        try:
            # Get conversation context
            conversation_context = self.get_conversation_context(user_id)
            
            # Get relevant memories - this is already async
            memories = await select_relevant_memories(username, user_message)
            
            # Get current story circle context - this is synchronous
            narrative_context = get_current_context()
            
            # Generate response - don't await since it's synchronous
            response = self.generator.generate_content(
                user_message=user_message,
                user_id=user_id,
                username=username,
                conversation_context=conversation_context,
                memories=memories,
                narrative_context=narrative_context
            )
            
            logger.info(f"Generated response: {response[:50]}...")
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Sorry, I couldn't process your request at the moment."
