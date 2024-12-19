import logging
from typing import Optional
from queue import Queue
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from src.config import Config

logger = logging.getLogger('AnnouncementBroadcaster')

class AnnouncementBroadcaster:
    """Singleton broadcaster to handle announcements across bots"""
    _instance = None
    _queue = Queue()
    _telegram_app = None
    _twitter_bot = None
    _chat_id = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnnouncementBroadcaster, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the broadcaster components"""
        try:
            self._telegram_app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()
            
            # Register the chatid command handler
            self._telegram_app.add_handler(CommandHandler("chatid", self.chatid_command))
            
            # Try to load chat ID from config
            if hasattr(Config, 'TELEGRAM_CHAT_ID') and Config.TELEGRAM_CHAT_ID:
                self._chat_id = Config.TELEGRAM_CHAT_ID
                logger.info(f"Loaded chat ID from config: {self._chat_id}")
            
            logger.info("Telegram application initialized in AnnouncementBroadcaster")
        except Exception as e:
            logger.error(f"Error initializing Telegram application: {e}", exc_info=True)
            self._telegram_app = None

    @classmethod
    def register_telegram_bot(cls, bot):
        """
        Maintained for backward compatibility.
        This method is now a no-op since Telegram app is initialized directly.
        """
        logger.info("register_telegram_bot called - this is now handled internally")
        pass

    @classmethod
    def register_twitter_bot(cls, bot):
        """Register twitter bot instance"""
        cls._twitter_bot = bot
        logger.info("Twitter bot registered with broadcaster")

    @classmethod
    def set_chat_id(cls, chat_id: str):
        """Set the chat ID for broadcasting"""
        if not chat_id:
            logger.error("Attempted to set empty chat ID")
            return False
            
        cls._chat_id = chat_id
        logger.info(f"Chat ID set to: {chat_id}")
        return True

    @classmethod
    async def chatid_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for the /chatid command."""
        if not update.effective_chat:
            logger.warning("No effective chat found in update")
            return

        chat_id = str(update.effective_chat.id)
        if cls.set_chat_id(chat_id):
            response_text = f"Chat ID set successfully: {chat_id}"
        else:
            response_text = "Failed to set chat ID. Please try again."

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=response_text
        )
        logger.info(f"Chat ID command responded with ID: {chat_id}")

    @classmethod
    async def broadcast(cls, message: str):
        """Broadcast message to all registered bots"""
        try:
            # First try instance chat_id, then config
            chat_id = cls._chat_id or getattr(Config, 'TELEGRAM_CHAT_ID', None)
            
            if not chat_id:
                logger.error("No chat ID available. Use /chatid command to set it or configure TELEGRAM_CHAT_ID")
                raise ValueError("No chat ID available for broadcasting. Use /chatid command to set it.")

            # Send to Telegram
            if cls._instance and cls._instance._telegram_app:
                await cls._instance._telegram_app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    disable_web_page_preview=True
                )
                logger.info(f"Announcement sent to Telegram chat {chat_id}")

            # Send to Twitter
            if cls._twitter_bot and cls._twitter_bot.tweet_manager:
                cls._twitter_bot.tweet_manager.send_tweet(message)
                logger.info("Announcement sent to Twitter")

        except ValueError as ve:
            logger.error(f"Configuration error in broadcast: {ve}")
            raise  # Re-raise to let caller handle it
        except Exception as e:
            logger.error(f"Error broadcasting announcement: {e}", exc_info=True)
            raise  # Re-raise to let caller handle it 