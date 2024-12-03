import random
import logging
import re
import requests
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ChallengeManager')

class ChallengeManager:
    def __init__(self):
        self._current_number = None
        self._min_range = 1
        self._max_range = 100
        self.generate_new_number()

    def generate_new_number(self) -> int:
        """Generate a new random number for the challenge"""
        self._current_number = random.randint(self._min_range, self._max_range)
        logger.info(f"New challenge number generated: {self._current_number}")
        return self._current_number

    def extract_solana_wallet(self, message: str) -> Optional[str]:
        """Extract Solana wallet address from message"""
        # Regex pattern for Solana wallet addresses
        solana_pattern = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
        match = re.search(solana_pattern, message)
        return match.group(0) if match else None

    def check_guess(self, message: str, username: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if message contains valid wallet and correct guess
        Returns: (is_valid_attempt, response_message, wallet_address)
        """
        wallet_address = self.extract_solana_wallet(message)
        
        if not wallet_address:
            return False, "hewwo! u need a sowana wawwet to pway! >w<", None

        # Extract number from message
        numbers = re.findall(r'\d+', message)
        if not numbers:
            return False, "hmm i dont see any numbews in ur message! twy again! :3", wallet_address

        guess = int(numbers[0])
        
        if guess == self._current_number:
            # Notify service and get transaction signature
            success, tx_signature = self.notify_winner(wallet_address)
            
            if success and tx_signature:
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
                "http://localhost:3000/trigger",
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