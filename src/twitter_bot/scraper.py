# src/twitter_bot/scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from typing import Optional
from .authenticator import Authenticator
from .tweets import TweetManager
import logging
import time
import os

# Configure logging
logger = logging.getLogger('Scraper')

class Scraper:
    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.driver = None
        self.auth = None
        self.tweets = None

    def _initialize_driver(self) -> bool:
        """Initialize Chrome driver with retry logic"""
        attempts = 3
        for attempt in range(attempts):
            try:
                chrome_options = Options()
                chrome_options.add_argument("--start-maximized")
                if self.proxy and self.proxy.strip() and self.proxy.lower() != "proxy_url_if_needed":
                    chrome_options.add_argument(f'--proxy-server={self.proxy}')
                
                try:
                    # Try to use webdriver_manager if available
                    try:
                        from webdriver_manager.chrome import ChromeDriverManager
                        self.driver = webdriver.Chrome(
                            service=ChromeService(ChromeDriverManager().install()), 
                            options=chrome_options
                        )
                        logger.info("Successfully initialized Chrome using WebDriver Manager")
                    except ImportError:
                        logger.warning("webdriver_manager not found. Please install with: pip install webdriver-manager")
                        logger.info("Falling back to default Chrome configuration")
                        chrome_options.add_argument("--log-level=3")
                        self.driver = webdriver.Chrome(options=chrome_options)
                        logger.info("Successfully initialized Chrome using default configuration")
                    return True
                    
                except Exception as e:
                    logger.error(f"Failed to initialize Chrome driver: {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{attempts} failed: {e}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                if attempt == attempts - 1:
                    return False
                time.sleep(2)
        return False

    def initialize(self) -> bool:
        """Initialize the scraper and authenticate with retry logic"""
        try:
            if not self._initialize_driver():
                logger.error("Failed to initialize driver")
                return False
                
            self.auth = Authenticator(self.driver)
            self.tweets = TweetManager(self.driver)
            
            # Try to load session
            if not self.auth.load_session():
                logger.info("No valid session found, attempting login...")
                if not self.auth.login():
                    logger.error("Login failed")
                    return False
            
            logger.info("Scraper initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing scraper: {e}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            return False

    def close(self):
        """Close the scraper and cleanup resources"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Driver closed successfully")
        except Exception as e:
            logger.error(f"Error closing driver: {e}")
            # Try to force kill if needed
            try:
                try:
                    import psutil
                    process = psutil.Process(self.driver.service.process.pid)
                    process.kill()
                    logger.info("Process killed using psutil")
                except ImportError:
                    logger.warning("psutil not found. Please install with: pip install psutil")
                    # Fallback to os._exit in extreme cases
                    logger.warning("Using fallback cleanup method")
                    if hasattr(self.driver, 'service') and hasattr(self.driver.service, 'process'):
                        os.kill(self.driver.service.process.pid, 9)
                        logger.info("Process killed using os.kill")
            except Exception as cleanup_error:
                logger.error(f"Failed to force kill process: {cleanup_error}")
