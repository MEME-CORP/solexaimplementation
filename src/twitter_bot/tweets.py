from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from typing import List, Optional
import os
import logging
from pathlib import Path
from src.database.supabase_client import DatabaseService
from src.challenge_manager import ChallengeManager

class TweetManager:
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.logger = logging.getLogger('TweetManager')
        self.processed_tweets = set()
        self.db = DatabaseService()
        self.load_processed_tweets()
        self.challenge_manager = None  # Will be set by TwitterBot
        
        # Process any pending tweets right after initialization
        self._process_pending_announcements()

    def _process_pending_announcements(self):
        """Process any pending announcements right after initialization"""
        from src.announcement_broadcaster import AnnouncementBroadcaster
        
        if not hasattr(AnnouncementBroadcaster, '_pending_tweets'):
            return
            
        pending = AnnouncementBroadcaster._pending_tweets[:]  # Make a copy
        
        for message in pending:
            try:
                self.send_tweet(message)
                AnnouncementBroadcaster._pending_tweets.remove(message)
                self.logger.info(f"Successfully posted pending announcement: {message[:30]}...")
            except Exception as e:
                self.logger.error(f"Failed to post pending announcement: {e}")

    def load_processed_tweets(self):
        """Load processed tweet IDs from database"""
        try:
            tweet_ids = self.db.get_processed_tweets()
            self.processed_tweets = set(tweet_ids)
            self.logger.info(f"Loaded {len(self.processed_tweets)} processed tweet IDs")
        except Exception as e:
            self.logger.error(f"Error loading processed tweets: {e}")
            self.processed_tweets = set()

    def save_processed_tweets(self):
        """Save processed tweet IDs to database"""
        try:
            # Convert set to list for database storage
            tweet_ids = list(self.processed_tweets)
            
            # Store in database using existing db service
            for tweet_id in tweet_ids:
                self.db.add_processed_tweet(tweet_id)
                
            self.logger.info(f"Saved {len(tweet_ids)} processed tweet IDs to database")
        except Exception as e:
            self.logger.error(f"Error saving processed tweets: {e}")

    def extract_tweet_id(self, article) -> str:
        """Extract tweet ID from article element"""
        try:
            timestamp = article.find_element(By.CSS_SELECTOR, "time").find_element(By.XPATH, "./..")
            url = timestamp.get_attribute("href")
            return url.split("/status/")[1]
        except Exception as e:
            self.logger.error(f"Error extracting tweet ID: {e}")
            return None

    def has_already_replied(self, article) -> bool:
        """Check if we've already replied to this tweet"""
        try:
            username = os.getenv("TWITTER_USERNAME", "agent47ai").lower()
            
            try:
                timestamp = article.find_element(By.CSS_SELECTOR, "time").find_element(By.XPATH, "./..")
                self.driver.execute_script("arguments[0].click();", timestamp)
                time.sleep(2)
                
                replies = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                
                for reply in replies:
                    try:
                        author_element = reply.find_element(By.CSS_SELECTOR, "[data-testid='User-Name']")
                        if f"@{username}" in author_element.text.lower():
                            self.logger.info(f"Found existing reply from {username}")
                            return True
                    except:
                        continue
                
                self.driver.get("https://twitter.com/notifications/mentions")
                time.sleep(2)
                return False
                
            except Exception as e:
                self.logger.error(f"Error checking replies in article: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in has_already_replied: {e}")
            return False

    def clear_text_box(self) -> None:
        try:
            tweet_box = self.driver.find_element(By.XPATH, "//div[@aria-label='Post text']")
            tweet_box.send_keys('\ue009' + 'a')  # Ctrl+A
            tweet_box.send_keys('\ue003')  # Backspace
            time.sleep(0.5)
        except:
            pass

    def send_tweet(self, content: str) -> str:
        """Send a new tweet with enhanced error handling and selectors. Returns tweet ID"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1} to send tweet...")
                
                # Navigate to home page
                self.logger.info("Navigating to home page...")
                self.driver.get("https://twitter.com/home")
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
                        self.logger.debug(f"Trying selector: {selector}")
                        if method == "xpath":
                            tweet_box = self.driver.find_element(By.XPATH, selector)
                        else:
                            tweet_box = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if tweet_box and tweet_box.is_displayed():
                            self.logger.info(f"Found tweet box with selector: {selector}")
                            break
                    except Exception as e:
                        self.logger.debug(f"Selector {selector} failed: {str(e)}")
                        continue
                
                if not tweet_box:
                    raise Exception("Could not find tweet input box")
                
                # Click and clear the input box
                self.logger.info("Clicking tweet box...")
                self.driver.execute_script("arguments[0].click();", tweet_box)
                time.sleep(1)
                self.clear_text_box()
                
                # Input content
                self.logger.info("Entering tweet content...")
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
                        self.logger.debug(f"Trying button selector: {selector}")
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                post_button = element
                                self.logger.info(f"Found post button with selector: {selector}")
                                break
                        if post_button:
                            break
                    except Exception as e:
                        self.logger.debug(f"Button selector {selector} failed: {str(e)}")
                        continue
                
                if not post_button:
                    raise Exception("Could not find post button")
                
                # Click post button
                self.logger.info("Clicking post button...")
                self.driver.execute_script("arguments[0].click();", post_button)
                time.sleep(3)  # Increased wait time
                
                # Get the tweet ID after posting
                self.logger.info("Getting tweet ID...")
                tweet_id = self._get_latest_tweet_id()
                
                if tweet_id:
                    self.logger.info(f"Tweet posted successfully with ID: {tweet_id}")
                    
                    # Check if this is a challenge announcement
                    if "chawwenge" in content.lower() and "guess" in content.lower():
                        self.logger.info("Challenge tweet detected - starting response monitoring")
                        self._handle_challenge_post(tweet_id, content)
                        
                    return tweet_id
                else:
                    raise Exception("Failed to get tweet ID")
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    self.logger.info("Retrying...")
                    time.sleep(2)
                    continue
                raise Exception(f"Failed to send tweet after {max_retries} attempts: {str(e)}")

    def _get_latest_tweet_id(self) -> Optional[str]:
        """Get the ID of the most recently posted tweet"""
        try:
            # Clear cache and reload profile
            self.driver.execute_script("window.location.reload(true);")
            self.driver.get("https://twitter.com/fwogai")
            time.sleep(3)
            
            # Get recent tweets with timestamps
            tweets = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
            if not tweets:
                return None
            
            # Get timestamps and IDs
            tweet_times = []
            for tweet in tweets[:5]:
                try:
                    time_element = tweet.find_element(By.CSS_SELECTOR, "time")
                    timestamp = time_element.get_attribute("datetime")
                    tweet_id = self.extract_tweet_id(tweet)
                    tweet_times.append((timestamp, tweet_id))
                except Exception as e:
                    self.logger.error(f"Error getting tweet details: {e}")
                    continue
                
            if not tweet_times:
                return None
            
            # Get most recent
            tweet_times.sort(reverse=True)
            return tweet_times[0][1]
            
        except Exception as e:
            self.logger.error(f"Error getting latest tweet ID: {e}")
            return None

    def _handle_challenge_post(self, tweet_id: str, content: str):
        """Handle a newly posted challenge tweet"""
        try:
            # Store the tweet ID in challenge manager
            if hasattr(self, 'challenge_manager') and self.challenge_manager:
                self.challenge_manager.set_active_challenge_tweet_id(tweet_id)
                
                # Create and start response manager directly
                from src.challenge_response_manager import ChallengeResponseManager
                response_manager = ChallengeResponseManager(
                    self.driver,
                    self.challenge_manager
                )
                
                # Start monitoring in background
                import asyncio
                asyncio.create_task(response_manager.start_response_monitoring())
                self.logger.info(f"Started challenge response monitoring for tweet {tweet_id}")
            else:
                self.logger.error("No challenge manager available")
                
        except Exception as e:
            self.logger.error(f"Error handling challenge post: {e}")

    def clean_content(self, content: str) -> str:
        """Clean tweet content"""
        content = content.split("**(")[0].strip()
        lines = content.split('\n')
        if len(lines) > 1:
            return lines[0].strip()
        return content.strip()

    def sanitize_text(self, text: str) -> str:
        """Sanitize text"""
        text = self.clean_content(text)
        return ''.join(char for char in text if ord(char) < 0xFFFF)

    def reply_to_tweet(self, tweet_data: dict, content: str) -> None:
        """Reply to a tweet"""
        max_retries = 3
        success = False
        
        try:
            content = self.sanitize_text(content)
            self.logger.info(f"Replying with content: {content}")
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        self.driver.get("https://twitter.com/notifications")
                        time.sleep(3)
                    
                    articles = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                    target_article = None
                    
                    for article in articles:
                        try:
                            tweet_id = self.extract_tweet_id(article)
                            if tweet_id == tweet_data['tweet_id']:
                                target_article = article
                                break
                        except:
                            continue
                    
                    if not target_article:
                        raise Exception("Could not find target tweet")
                    
                    reply_button = target_article.find_element(By.CSS_SELECTOR, "[data-testid='reply']")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", reply_button)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", reply_button)
                    time.sleep(2)
                    
                    editor = self.driver.find_element(By.CSS_SELECTOR, "div[data-testid='tweetTextarea_0']")
                    self.driver.execute_script("arguments[0].click();", editor)
                    time.sleep(1)
                    
                    editor.send_keys('\ue009' + 'a')
                    editor.send_keys('\ue003')
                    time.sleep(1)
                    
                    editor.send_keys(content)
                    time.sleep(1)
                    
                    post_button = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='tweetButton']")
                    self.driver.execute_script("arguments[0].click();", post_button)
                    time.sleep(3)
                    
                    success = True
                    self.logger.info(f"Successfully replied to tweet {tweet_data['tweet_id']}")
                    break
                    
                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    raise
                
            if success:
                self.mark_tweet_processed(tweet_data['tweet_id'])
                self.logger.info(f"Marked tweet {tweet_data['tweet_id']} as processed")
                
        except Exception as e:
            self.logger.error(f"Error replying to tweet: {e}")
        finally:
            self.logger.info("Returning to notifications page...")
            self.driver.get("https://twitter.com/notifications")
            time.sleep(3)

    async def check_notifications(self) -> List[dict]:
        """Check notifications for mentions and process any challenge attempts"""
        try:
            self.driver.get("https://twitter.com/notifications")
            time.sleep(5)
            
            username = os.getenv("TWITTER_USERNAME", "agent47ai").lower()
            self.logger.info(f"Checking notifications for @{username}")
            
            notifications = []
            processed_count = 0
            max_scroll_attempts = 5
            scroll_attempt = 0
            
            while scroll_attempt < max_scroll_attempts:
                articles = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
                self.logger.info(f"Found {len(articles)} articles, processed {processed_count}")
                
                if processed_count >= len(articles):
                    break
                
                for article in articles[processed_count:]:
                    try:
                        tweet_id = self.extract_tweet_id(article)
                        if not tweet_id or self.is_tweet_processed(tweet_id):
                            continue
                        
                        tweet_text = article.find_element(By.CSS_SELECTOR, "div[data-testid='tweetText']").text
                        
                        notification = {
                            "text": tweet_text,
                            "tweet_id": tweet_id,
                            "element": article
                        }
                        
                        # Check if it's a mention
                        if f"@{username}" in tweet_text.lower():
                            notifications.append(notification)
                        
                        # Process as potential challenge reply
                        await self.process_challenge_reply(notification)
                        
                        # Mark as processed
                        self.mark_tweet_processed(tweet_id)
                        
                    except Exception as e:
                        self.logger.error(f"Error processing article: {e}")
                        continue
                
                processed_count = len(articles)
                
                if articles:
                    try:
                        last_article = articles[-1]
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", last_article)
                        time.sleep(2)
                        scroll_attempt += 1
                    except Exception as e:
                        self.logger.error(f"Error scrolling: {e}")
                        break
                else:
                    break

            return notifications

        except Exception as e:
            self.logger.error(f"Error checking notifications: {e}")
            return []

    def check_and_process_mentions(self, generator):
        """Check and process mentions"""
        try:
            notifications = self.check_notifications()
            
            if notifications:
                self.logger.info(f"Processing {len(notifications)} mentions...")
                for notification in notifications:
                    try:
                        # Use the working message format
                        reply_content = generator.generate_content(
                            user_message=f"reply to: {notification['text']}", 
                            topic='',  # Empty for replies
                            conversation_context='',  # Could add previous context if needed
                            username=''  # Could add username if needed
                        )
                        
                        if reply_content and isinstance(reply_content, str):
                            self.logger.info(f"Generated reply: {reply_content[:50]}...")
                            self.reply_to_tweet(notification, reply_content)
                            # Explicitly save processed tweets after each reply
                            self.processed_tweets.add(notification['tweet_id'])
                            self.save_processed_tweets()
                            self.logger.info(f"Replied to tweet ID: {notification['tweet_id']}")
                            time.sleep(2)
                    except Exception as e:
                        self.logger.error(f"Error processing notification: {e}")
                        continue
            else:
                self.logger.info("No new mentions to process")
                
        except Exception as e:
            self.logger.error(f"Error in check_and_process_mentions: {e}")

    def is_tweet_processed(self, tweet_id: str) -> bool:
        """Check if a tweet has already been processed"""
        return tweet_id in self.processed_tweets

    def mark_tweet_processed(self, tweet_id: str) -> None:
        """Mark a tweet as processed and save to database"""
        if not tweet_id:
            return
            
        self.processed_tweets.add(tweet_id)
        try:
            # Save individual tweet right after processing
            self.db.add_processed_tweet(tweet_id)
            self.logger.info(f"Marked tweet {tweet_id} as processed")
        except Exception as e:
            self.logger.error(f"Error marking tweet as processed: {e}")

    async def process_challenge_reply(self, notification: dict) -> None:
        """Process a reply to see if it's a challenge attempt"""
        try:
            message = notification['text']
            username = notification.get('username', 'fwiend')
            
            # First check if there's a wallet address
            wallet_address = self.challenge_manager.extract_solana_wallet(message)
            
            # If no wallet found, treat as regular message
            if not wallet_address:
                reply_content = self.generator.generate_content(
                    user_message=f"reply to: {message}",
                    conversation_context='',
                    username=username
                )
                self.reply_to_tweet(notification, reply_content)
                return
            
            # If challenge is not active, respond accordingly
            if not self.challenge_manager.is_challenge_active():
                response = "sowwy, thewe's no active chawwenge wight now! >w< stay tuned for the next one!"
                self.reply_to_tweet(notification, response)
                return
            
            # Process the guess
            is_valid, response, _ = await self.challenge_manager.check_guess(message, username)
            self.reply_to_tweet(notification, response)
            
        except Exception as e:
            self.logger.error(f"Error processing challenge reply: {e}")