import logging
from typing import Optional
from queue import Queue
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from src.config import Config
from selenium.webdriver.common.by import By
import time
from src.challenge_response_manager import ChallengeResponseManager

logger = logging.getLogger('AnnouncementBroadcaster')

class AnnouncementBroadcaster:
    """Singleton broadcaster to handle announcements across bots"""
    _instance = None
    _queue = Queue()
    _telegram_app = None
    _twitter_driver = None
    _twitter_bot = None  # Keep this for backward compatibility
    _chat_id = None
    _pending_tweets = []  # Class variable to store pending tweets
    _challenge_response_manager = None  # Add this line

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
        """Register twitter bot instance and initialize challenge response manager"""
        cls._twitter_bot = bot
        # Set the driver from the bot's tweet manager
        if hasattr(bot, 'tweet_manager') and hasattr(bot.tweet_manager, 'driver'):
            cls._twitter_driver = bot.tweet_manager.driver
            logger.info("Twitter WebDriver registered from bot's tweet manager")
            
            # Initialize ChallengeResponseManager with the driver and challenge manager
            if hasattr(bot, 'challenge_manager'):
                cls._challenge_response_manager = ChallengeResponseManager(
                    cls._twitter_driver, 
                    bot.challenge_manager
                )
                logger.info("Challenge Response Manager initialized with Twitter driver")
            else:
                logger.error("Bot has no challenge_manager attribute")
            
        logger.info("Twitter bot registered with broadcaster")

    @classmethod
    def set_twitter_driver(cls, driver):
        """Set Selenium WebDriver for Twitter"""
        cls._twitter_driver = driver
        logger.info("Twitter WebDriver registered with broadcaster")

    @classmethod
    async def broadcast(cls, message: str):
        """Broadcast message to all registered bots"""
        try:
            # First try instance chat_id, then config
            chat_id = cls._chat_id or getattr(Config, 'TELEGRAM_CHAT_ID', None)
            
            if not chat_id:
                logger.error("No chat ID available. Use /chatid command to set it or configure TELEGRAM_CHAT_ID")
                raise ValueError("No chat ID available for broadcasting")

            # Send to Telegram
            telegram_success = False
            if cls._instance and cls._instance._telegram_app:
                try:
                    await cls._instance._telegram_app.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        disable_web_page_preview=True
                    )
                    telegram_success = True
                    logger.info(f"Successfully sent announcement to Telegram chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send Telegram message: {e}")
                    # Don't raise here, try Twitter anyway

            # Handle Twitter posting
            twitter_success = False
            if cls._twitter_driver:
                try:
                    await cls._send_tweet(message)
                    twitter_success = True
                    logger.info("Successfully sent announcement to Twitter")
                except Exception as e:
                    logger.error(f"Error sending tweet: {e}")
                    if message not in cls._pending_tweets:
                        cls._pending_tweets.append(message)
                        logger.info("Message stored for Twitter posting after error")
            else:
                if message not in cls._pending_tweets:
                    cls._pending_tweets.append(message)
                    logger.info("Message stored for Twitter posting (no driver available)")

            # Log overall broadcast status
            if telegram_success or twitter_success:
                logger.info("Broadcast completed successfully to at least one platform")
            else:
                logger.warning("Broadcast failed on all platforms")

            return telegram_success or twitter_success

        except Exception as e:
            logger.error(f"Critical error in broadcast: {e}", exc_info=True)
            raise

    @classmethod
    async def _send_tweet(cls, content: str):
        """Send tweet using Selenium WebDriver"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempt {attempt + 1} to send tweet...")
                
                # Navigate to home page
                logger.info("Navigating to home page...")
                cls._twitter_driver.get("https://twitter.com/home")
                time.sleep(3)
                
                # Core working selectors from proven implementation
                tweet_box_selectors = [
                    ("xpath", "//div[@aria-label='Post text']"),
                    ("xpath", "//div[@aria-label='Tweet text']"),
                    ("css", "div[aria-label='Post text']"),
                    ("css", "div[data-testid='tweetTextarea_0']"),
                    ("css", "div[role='textbox'][aria-label='Post text']")
                ]
                
                # Find tweet box using proven selectors
                tweet_box = None
                for method, selector in tweet_box_selectors:
                    try:
                        if method == "xpath":
                            tweet_box = cls._twitter_driver.find_element(By.XPATH, selector)
                        else:
                            tweet_box = cls._twitter_driver.find_element(By.CSS_SELECTOR, selector)
                        if tweet_box and tweet_box.is_displayed():
                            logger.info(f"Found tweet box with selector: {selector}")
                            break
                    except Exception as e:
                        continue
                
                if not tweet_box:
                    raise Exception("Could not find tweet input box")
                
                # Click and clear the input box
                logger.info("Clicking tweet box...")
                cls._twitter_driver.execute_script("arguments[0].click();", tweet_box)
                time.sleep(1)
                
                # Clear text box
                tweet_box.send_keys('\ue009' + 'a')  # Ctrl+A
                tweet_box.send_keys('\ue003')  # Backspace
                time.sleep(0.5)
                
                # Input content
                logger.info("Entering tweet content...")
                tweet_box.send_keys(content)
                time.sleep(1)
                
                # Use proven button selectors
                button_selectors = [
                    ("css", "[data-testid='tweetButton']"),
                    ("css", "div[role='button'][data-testid='tweetButtonInline']"),
                    ("css", "div.css-175oi2r.r-kemksi.r-jumn1c.r-xd6kpl.r-gtdqiz.r-ipm5af.r-184en5c > div:nth-child(2) > div > div > div > button")
                ]
                
                # Find post button
                post_button = None
                for method, selector in button_selectors:
                    try:
                        elements = cls._twitter_driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                post_button = element
                                logger.info(f"Found post button with selector: {selector}")
                                break
                        if post_button:
                            break
                    except Exception as e:
                        continue
                
                if not post_button:
                    raise Exception("Could not find post button")
                
                # Click post button
                logger.info("Clicking post button...")
                cls._twitter_driver.execute_script("arguments[0].click();", post_button)
                time.sleep(2)
                
                logger.info("Tweet posted successfully")
                return
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info("Retrying...")
                    time.sleep(2)
                    continue
                raise Exception(f"Failed to send tweet after {max_retries} attempts: {str(e)}")

    @classmethod
    async def process_pending_tweets(cls):
        """Process any pending tweets once Twitter is ready"""
        if not cls._twitter_driver or not cls._pending_tweets:
            return

        for message in cls._pending_tweets[:]:  # Create a copy to iterate
            try:
                await cls._send_tweet(message)
                cls._pending_tweets.remove(message)
                logger.info("Successfully posted pending tweet")
            except Exception as e:
                logger.error(f"Error posting pending tweet: {e}")

    # Keep existing Telegram methods unchanged
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
    def set_chat_id(cls, chat_id: str):
        """Set the chat ID for broadcasting"""
        if not chat_id:
            logger.error("Attempted to set empty chat ID")
            return False
            
        cls._chat_id = chat_id
        logger.info(f"Chat ID set to: {chat_id}")
        return True

    @classmethod
    async def broadcast_challenge(cls, message: str) -> Optional[str]:
        """Broadcast challenge announcement and return the tweet ID"""
        try:
            tweet_id = None
            
            # Send to Telegram
            if cls._instance and cls._instance._telegram_app and cls._chat_id:
                try:
                    await cls._instance._telegram_app.bot.send_message(
                        chat_id=cls._chat_id,
                        text=message,
                        disable_web_page_preview=True
                    )
                    logger.info(f"Successfully sent challenge to Telegram chat {cls._chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send Telegram message: {e}")

            # Handle Twitter posting and get tweet ID
            if cls._twitter_driver:
                try:
                    # Use the modified send_tweet method that returns the tweet ID
                    tweet_id = await cls._send_tweet_and_get_id(message)
                    if tweet_id:
                        logger.info(f"Successfully posted challenge to Twitter with ID: {tweet_id}")
                        
                        # Store the tweet ID in the challenge manager
                        if cls._challenge_response_manager:
                            if cls._challenge_response_manager.challenge_manager:
                                logger.info(f"Setting active challenge tweet ID: {tweet_id}")
                                cls._challenge_response_manager.challenge_manager.set_active_challenge_tweet_id(tweet_id)
                                
                                # Start monitoring in background task
                                logger.info("Starting challenge response monitoring...")
                                asyncio.create_task(cls._challenge_response_manager.start_response_monitoring())
                            else:
                                logger.error("Challenge manager not initialized in response manager")
                        else:
                            logger.error("No challenge response manager registered")
                    else:
                        logger.error("Failed to get tweet ID for challenge")
                        
                except Exception as e:
                    logger.error(f"Error sending challenge tweet: {e}", exc_info=True)
                
            return tweet_id

        except Exception as e:
            logger.error(f"Critical error in broadcast_challenge: {e}", exc_info=True)
            return None

    @classmethod
    async def _send_tweet_and_get_id(cls, content: str) -> Optional[str]:
        """Send tweet and return its ID"""
        try:
            if cls._twitter_driver and hasattr(cls._twitter_driver, 'send_tweet'):
                tweet_id = cls._twitter_driver.send_tweet(content)
                if tweet_id:
                    logger.info(f"Got tweet ID after posting: {tweet_id}")
                    return tweet_id
            return None
        except Exception as e:
            logger.error(f"Error in _send_tweet_and_get_id: {e}")
            return None

    @classmethod
    def register_challenge_response_manager(cls, manager: ChallengeResponseManager):
        """Register the challenge response manager"""
        cls._challenge_response_manager = manager
        logger.info("Challenge Response Manager registered with broadcaster")