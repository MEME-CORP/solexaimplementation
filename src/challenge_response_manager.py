# challenge_response_manager.py

import logging
import time
from typing import List, Dict
from selenium.webdriver.common.by import By
from src.database.supabase_client import DatabaseService
from src.challenge_manager import ChallengeManager
import asyncio

class ChallengeResponseManager:
    """
    This class is responsible for:
      - Tracking the tweet ID of the active challenge announcement
      - Fetching replies for that specific tweet
      - Checking if any replies contain a valid guess
      - Invoking the ChallengeManager's logic to validate and process the guess
      - Marking replies as processed to avoid repetition
    """
    def __init__(self, driver, challenge_manager):
        self.driver = driver
        self.challenge_manager = challenge_manager
        self.logger = logging.getLogger("ChallengeResponseManager")
        self._check_interval = 60  # Check every minute
        self._running = False
        self._last_check_time = None
        self._current_tweet_id = None
        
    async def start_response_monitoring(self):
        """Start monitoring responses every minute"""
        if self._running:
            self.logger.warning("Response monitoring already active")
            return

        # Verify components
        if not self.driver or not self.challenge_manager:
            self.logger.error("Missing required components")
            return
            
        self._running = True
        self._last_check_time = time.time()
        self.logger.info("Starting challenge response monitoring")
        
        while self._running:
            try:
                tweet_id = self.challenge_manager.get_active_challenge_tweet_id()
                if not tweet_id:
                    await asyncio.sleep(self._check_interval)
                    continue
                    
                # Only process if tweet ID changed
                if tweet_id != self._current_tweet_id:
                    self._current_tweet_id = tweet_id
                    self.logger.info(f"New challenge tweet detected: {tweet_id}")
                    
                self.logger.info(f"Checking responses for tweet: {tweet_id}")
                self.process_challenge_responses(tweet_id)
                self._last_check_time = time.time()
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                
            await asyncio.sleep(self._check_interval)

    def stop_response_monitoring(self):
        """Stop monitoring responses"""
        if not self._running:
            self.logger.warning("Response monitoring is not running")
            return
            
        self._running = False
        self.logger.info("Stopping response monitoring...")

    def verify_monitoring_status(self) -> bool:
        """Verify that response monitoring is active and working"""
        if not self._running:
            self.logger.error("Challenge response monitoring is not running")
            return False
        
        if not self.challenge_manager.get_active_challenge_tweet_id():
            self.logger.error("No active challenge tweet ID found")
            return False
        
        self.logger.info("Challenge response monitoring is active and working")
        return True
