# src/twitter_bot/twitter_bot.py

import logging
import time
import random
from datetime import datetime
from pathlib import Path
import json
import os
from dotenv import load_dotenv
from src.ai_generator import AIGenerator
from .scraper import Scraper
from .tweets import TweetManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TwitterBot')

class TwitterBot:
    def __init__(self, handle_signals=False):
        logger.info("Initializing Twitter bot...")
        
        # Get the absolute path to the .env file
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / '.env'
        
        logger.info("Loading environment variables...")
        if not load_dotenv(dotenv_path=env_path, override=True):
            raise ValueError(f"Could not load .env file from {env_path}")
        
        # Initialize components
        self.generator = AIGenerator(mode='twitter')
        self.proxy = os.getenv("PROXY_URL")
        self.scraper = None
        self.tweet_manager = None
        self.running = False
        self.is_cleaning_up = False
        
        logger.info("Twitter bot initialization complete!")

    def initialize(self) -> bool:
        """Initialize the Twitter bot components"""
        try:
            if not self.generator:
                logger.error("AI Generator not initialized")
                return False

            if self.scraper is None:
                self.scraper = Scraper(proxy=self.proxy)
                if not self.scraper.initialize():
                    logger.error("Failed to initialize scraper")
                    return False

            if self.tweet_manager is None:
                if not self.scraper or not self.scraper.driver:
                    logger.error("Scraper or driver not properly initialized")
                    return False
                self.tweet_manager = TweetManager(self.scraper.driver)
                
            # Verify all components
            if not all([self.generator, self.scraper, self.tweet_manager]):
                logger.error("Not all components initialized properly")
                return False
                
            logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Twitter bot: {e}")
            return False

    def run(self):
        """Run the main loop of the Twitter bot"""
        try:
            logger.info("Initializing Twitter bot components...")
            if not self.initialize():
                logger.error("Failed to initialize Twitter bot components")
                return

            logger.info("Twitter bot initialized successfully!")
            self.running = True
            
            # Execute initial tasks
            logger.info("=== Initial Tasks ===")
            if self.tweet_manager and self.generator:
                self.tweet_manager.check_and_process_mentions(self.generator)
                self.generate_and_send_tweet()
            
            # Set timers
            last_tweet_time = time.time()
            last_notification_check = time.time()
            tweet_interval = random.randint(300, 1800)  # 5-30 minutes
            notification_interval = 300  # 5 minutes

            logger.info(f"Next tweet in {tweet_interval/60:.1f} minutes")
            logger.info(f"Next notification check in {notification_interval/60:.1f} minutes")

            while self.running:
                try:
                    if not all([self.generator, self.scraper, self.tweet_manager]):
                        logger.error("Critical components lost during runtime")
                        if not self.initialize():  # Try to reinitialize
                            logger.error("Could not recover components")
                            break

                    current_time = time.time()

                    if self.is_cleaning_up:
                        logger.info("Cleanup in progress. Exiting run loop.")
                        break

                    # Check notifications
                    if current_time - last_notification_check >= notification_interval:
                        logger.info("=== Checking Notifications ===")
                        if self.tweet_manager and self.generator:
                            try:
                                self.tweet_manager.check_and_process_mentions(self.generator)
                            except Exception as e:
                                logger.error(f"Error checking notifications: {e}")
                        last_notification_check = current_time
                        logger.info(f"Next notification check in {notification_interval/60:.1f} minutes")

                    # Post tweets
                    if current_time - last_tweet_time >= tweet_interval:
                        logger.info("=== Generating Tweet ===")
                        try:
                            self.generate_and_send_tweet()
                        except Exception as e:
                            logger.error(f"Error generating tweet: {e}")
                        last_tweet_time = current_time
                        tweet_interval = random.randint(300, 1800)
                        logger.info(f"Next tweet in {tweet_interval/60:.1f} minutes")

                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Error in run loop: {e}")
                    time.sleep(10)

        except Exception as e:
            logger.error(f"Critical error in Twitter bot: {e}")
        finally:
            self.stop()
            if not self.is_cleaning_up:
                self.cleanup()

    def generate_and_send_tweet(self):
        """Generate and send a tweet"""
        if not all([self.generator, self.tweet_manager]):
            logger.error("Cannot generate and send tweet - missing components")
            return

        try:
            # Load topics from data directory
            topics_path = Path(__file__).parent.parent.parent / 'data' / 'topics.json'
            
            if not topics_path.exists():
                logger.error(f"Topics file not found at {topics_path}")
                return
            
            with open(topics_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                topics = data.get('topics', [])
                if not topics:
                    logger.error("No topics found in topics.json")
                    return

            topic = random.choice(topics)['topic']
            logger.info(f"Selected topic: {topic}")

            # Generate content using AIGenerator
            content = self.generator.generate_content(
                topic=topic,
                conversation_context='',
                username=''
            )

            if not content or not isinstance(content, str):
                logger.error("No valid content generated")
                return

            self.tweet_manager.send_tweet(content)
            logger.info("Tweet posted successfully")

        except Exception as e:
            logger.error(f"Error generating/sending tweet: {e}")

    def stop(self):
        """Stop the bot gracefully"""
        logger.info("Stopping Twitter bot...")
        self.running = False
        self.is_cleaning_up = True

    def cleanup(self):
        """Cleanup resources"""
        if self.is_cleaning_up:
            logger.info("Cleanup already in progress.")
            return

        self.is_cleaning_up = True
        try:
            logger.info("Starting cleanup process...")
            self.running = False
            
            if self.scraper:
                logger.info("Closing scraper...")
                try:
                    self.scraper.close()
                except Exception as e:
                    logger.error(f"Error closing scraper: {e}")
                finally:
                    self.scraper = None
            
            logger.info("Cleanup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            os._exit(0)
