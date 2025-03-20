# src/twitter_bot/authenticator.py

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
import logging
import json
import os
from src.config import Config

# Configure logging
logger = logging.getLogger('Authenticator')

class Authenticator:
    def __init__(self, driver):
        self.driver = driver
        self.username = Config.TWITTER_USERNAME
        self.password = Config.TWITTER_PASSWORD
        self.email = Config.TWITTER_EMAIL
        self.session_file = os.path.join(os.path.dirname(__file__), "twitter_session.json")

    def save_cookies(self, cookies, file_path):
        """Save cookies to a file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(cookies, f)
            logger.info("Cookies saved successfully")
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")

    def load_cookies(self, file_path):
        """Load cookies from a file"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
        return None

    def save_session(self):
        """Save the current session cookies"""
        cookies = self.driver.get_cookies()
        self.save_cookies(cookies, self.session_file)
        logger.info("Session saved successfully!")

    def load_session(self) -> bool:
        """Load and verify a saved session"""
        cookies = self.load_cookies(self.session_file)
        if not cookies:
            logger.info("No saved session found.")
            return False

        try:
            # Load the base URL first
            self.driver.get("https://twitter.com")
            
            # Add the saved cookies
            for cookie in cookies:
                if isinstance(cookie.get('expiry', None), float):
                    cookie['expiry'] = int(cookie['expiry'])
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"Could not add cookie: {e}")

            # Refresh and verify login status
            self.driver.get("https://twitter.com/home")
            time.sleep(3)
            
            # Verify we're logged in by looking for the post box
            self.driver.find_element(By.XPATH, "//div[@aria-label='Post text']")
            logger.info("Session restored successfully!")
            return True

        except NoSuchElementException:
            logger.warning("Saved session is invalid or expired.")
            # Delete the invalid session file
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
            return False
        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return False

    def login(self):
        """Login to Twitter with provided credentials"""
        try:
            # First try to load existing session
            if self.load_session():
                return True

            logger.info("Attempting to log in to Twitter.")
            self.driver.get("https://twitter.com/login")
            time.sleep(3)  # Wait for page to load

            # Enter username
            username_field = self.driver.find_element(By.NAME, "text")
            username_field.send_keys(self.username)
            username_field.send_keys(Keys.RETURN)
            time.sleep(2)

            # Enter password
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.send_keys(self.password)
            password_field.send_keys(Keys.RETURN)
            time.sleep(5)  # Wait for login to complete
            
            # Note: We don't check for verification here to avoid circular dependency
            # Verification is handled at the TwitterBot level
            
            # Verify login success
            try:
                self.driver.find_element(By.XPATH, "//div[@aria-label='Post text']")
                logger.info("Login successful!")
                # Save session after successful login
                self.save_session()
                return True
            except NoSuchElementException:
                logger.error("Login failed - could not find post box")
                return False

        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def logout(self):
        """Log out from Twitter"""
        try:
            self.driver.get("https://twitter.com/logout")
            time.sleep(2)
            confirm_button = self.driver.find_element(By.XPATH, "//div[@data-testid='confirmationSheetConfirm']")
            confirm_button.click()
            time.sleep(3)
            # Delete session file
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
            logger.info("Logged out successfully")
        except Exception as e:
            logger.error(f"Error during logout: {e}")

    def complete_login_after_verification(self):
        """Complete the login process after verification without restarting the browser"""
        try:
            # Verify we're logged in by looking for the post box
            time.sleep(3)  # Wait for page to load completely after verification
            
            try:
                self.driver.find_element(By.XPATH, "//div[@aria-label='Post text']")
                logger.info("Login successful after verification!")
                # Save session after successful login
                self.save_session()
                return True
            except NoSuchElementException:
                # We might need to navigate to home
                self.driver.get("https://twitter.com/home")
                time.sleep(3)
                
                try:
                    self.driver.find_element(By.XPATH, "//div[@aria-label='Post text']")
                    logger.info("Login successful after navigating to home!")
                    self.save_session()
                    return True
                except NoSuchElementException:
                    logger.error("Login failed after verification - could not find post box")
                    return False
                
        except Exception as e:
            logger.error(f"Error completing login after verification: {e}")
            return False
