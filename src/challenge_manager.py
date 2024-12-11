import random
import logging
import re
import requests
from typing import Optional, Tuple
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ChallengeManager')

class ChallengeManager:
    def __init__(self):
        self._current_number = None
        self._min_range = 1
        self._max_range = 100
        self._challenge_active = False
        self._next_challenge_time = None
        self._challenge_winner = None
        self._min_hours = 18
        self._max_hours = 30
        
    def _schedule_next_challenge(self):
        """Schedule the next challenge"""
        hours = random.uniform(self._min_hours, self._max_hours)
        self._next_challenge_time = datetime.now() + timedelta(hours=hours)
        logger.info(f"Next challenge scheduled for: {self._next_challenge_time}")

    def start_challenge(self, generate_new_number: bool = True) -> bool:
        """
        Start a new challenge if conditions are met
        Args:
            generate_new_number: Whether to generate a new number (False for testing)
        Returns:
            bool: Whether challenge was started successfully
        """
        if self._challenge_active:
            logger.info("Challenge already active")
            return False
            
        if self._next_challenge_time and datetime.now() < self._next_challenge_time:
            logger.info(f"Too early for next challenge. Scheduled for: {self._next_challenge_time}")
            return False
            
        self._challenge_active = True
        self._challenge_winner = None
        
        if generate_new_number:
            self.generate_new_number()
            
        self._schedule_next_challenge()
        logger.info("New challenge started!")
        return True

    def is_challenge_active(self) -> bool:
        """Check if challenge is currently active"""
        return self._challenge_active

    def get_next_challenge_time(self) -> Optional[datetime]:
        """Get the time of the next challenge"""
        return self._next_challenge_time

    def generate_new_number(self) -> int:
        """Generate a new random number for the challenge"""
        self._current_number = random.randint(self._min_range, self._max_range)
        logger.info(f"New challenge number generated: {self._current_number}")
        return self._current_number

    def extract_solana_wallet(self, message: str) -> Optional[str]:
        """
        Extract Solana wallet address from message using precise criteria:
        - 44 characters exactly
        - Base58 encoding (excludes: 0, O, I, l)
        - Alphanumeric with both cases allowed
        - Must match exact Base58 character set
        
        Returns: Wallet address if found and valid, None otherwise
        """
        try:
            # Define valid Base58 character set (excluding 0, O, I, l)
            valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
            invalid_chars = set('0OIl')
            
            # Find exact 44-character strings with word boundaries
            # \b ensures we match whole words, not parts of longer strings
            matches = re.finditer(r'\b[A-Za-z0-9]{44}\b', message)
            
            for match in matches:
                potential_address = match.group(0)
                
                # Log potential match for debugging
                logger.debug(f"Checking potential address: {potential_address}")
                
                # First check: exact length
                if len(potential_address) != 44:
                    logger.debug(f"Invalid length: {len(potential_address)}")
                    continue
                    
                # Second check: character set validation
                if not set(potential_address).issubset(valid_chars):
                    logger.debug("Invalid characters found")
                    continue
                    
                # Third check: no invalid characters
                if set(potential_address).intersection(invalid_chars):
                    logger.debug("Excluded characters found")
                    continue
                
                # All validation passed
                logger.info(f"Valid Solana wallet address found: {potential_address}")
                return potential_address
                    
            logger.debug("No valid Solana wallet address found in message")
            return None
                
        except Exception as e:
            logger.error(f"Error extracting Solana wallet address: {e}")
            return None

    def check_guess(self, message: str, username: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if message contains valid wallet and correct guess
        Returns: (is_valid_attempt, response_message, wallet_address)
        """
        # If challenge is not active or already won, return None to let AI handle it
        if not self._challenge_active or self._challenge_winner:
            return False, None, None

        wallet_address = self.extract_solana_wallet(message)
        
        if not wallet_address:
            return False, None, None

        numbers = re.findall(r'\d+', message)
        if not numbers:
            return False, "hmm i dont see any numbews in ur message! twy again! :3", wallet_address

        guess = int(numbers[0])
        
        if guess == self._current_number:
            success, tx_signature = self.notify_winner(wallet_address)
            
            if success and tx_signature:
                # Store winner and deactivate challenge
                self._challenge_winner = username
                self._challenge_active = False
                
                response = (
                    f"YAYYY!! @{username} found the wight numbew ({self._current_number})!! "
                    f"0.1 SOL has been sent to ur wawwet! "
                    f"check the pinned message i wiww post in the nex few minutes for ur twansaction detaiws! ^w^"
                )
            else:
                response = "OMG u found the wight numbew but something went wong with the pwize! pwease contact suppowt! >.<"
                
            return True, response, wallet_address
        else:
            response = "sowwy, that's not the wight numbew! keep twying! >w<"
            return False, response, wallet_address

    def notify_winner(self, wallet_address: str) -> Tuple[bool, Optional[str]]:
        """
        Notify external service about winner and get transaction signature
        Returns: (success, transaction_signature)
        """
        try:
            payload = {
                "username": "twitter_winner",
                "challengeCompleted": True,
                "solanaAddress": wallet_address
            }
            
            response = requests.post(
                "https://web3-agent.onrender.com/trigger",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                try:
                    # Extract transaction signature from response
                    response_data = response.json()
                    tx_signature = response_data.get('signature')
                    if tx_signature:
                        logger.info(f"Successfully notified winner: {wallet_address}")
                        return True, tx_signature
                except Exception as e:
                    logger.error(f"Error parsing response: {e}")
            
            logger.error(f"Failed to notify winner. Status code: {response.status_code}")
            return False, None
                
        except Exception as e:
            logger.error(f"Error notifying winner: {e}")
            return False, None

    def generate_winner_announcement(self, username: str, winning_number: int, tx_signature: str) -> str:
        """Generate announcement tweet for winner"""
        return (
            f"congwatuwations @{username} for winning the chawwenge!! "
            f"they found the wight numbew ({winning_number}) and won 0.1 SOL!! "
            f"hewe's the twansaction: https://solscan.io/tx/{tx_signature} ^w^"
        )