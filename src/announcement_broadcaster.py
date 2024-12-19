import logging
from typing import Optional
from queue import Queue
import asyncio

logger = logging.getLogger('AnnouncementBroadcaster')

class AnnouncementBroadcaster:
    """Singleton broadcaster to handle announcements across bots"""
    _instance = None
    _queue = Queue()
    _telegram_bot = None
    _twitter_bot = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnnouncementBroadcaster, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register_telegram_bot(cls, bot):
        """Register telegram bot instance"""
        cls._telegram_bot = bot
        logger.info("Telegram bot registered with broadcaster")

    @classmethod
    def register_twitter_bot(cls, bot):
        """Register twitter bot instance"""
        cls._twitter_bot = bot
        logger.info("Twitter bot registered with broadcaster")

    @classmethod
    async def broadcast(cls, message: str):
        """Broadcast message to all registered bots"""
        try:
            if cls._telegram_bot:
                # Use telegram bot's default chat ID from config
                await cls._telegram_bot.application.bot.send_message(
                    chat_id=cls._telegram_bot.application.bot.defaults.chat_id,
                    text=message
                )
                logger.info("Announcement sent to Telegram")

            if cls._twitter_bot and cls._twitter_bot.tweet_manager:
                cls._twitter_bot.tweet_manager.send_tweet(message)
                logger.info("Announcement sent to Twitter")

        except Exception as e:
            logger.error(f"Error broadcasting announcement: {e}") 