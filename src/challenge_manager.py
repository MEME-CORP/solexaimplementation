import random
import logging
import re
import requests
from typing import Optional, Tuple, Dict
from datetime import datetime, timedelta
from src.wallet_manager import WalletManager
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ChallengeManager')

class ChallengeManager:
    def __init__(self):
        """Initialize ChallengeManager"""
        self._current_number = None
        self._min_range = 1
        self._max_range = 100
        self._challenge_active = False
        self._next_challenge_time = None
        self._challenge_winner = None
        self._min_hours = 18
        self._max_hours = 30
        
        # Modified properties for correct progression
        self._challenge_count = 0
        self._current_reward = Decimal('0.1')  # Starting reward
        self._base_token_percentage = Decimal('0.5')  # Base percentage for second challenge
        self._base_transfer_amount = Decimal('0.01')  # Base transfer for second challenge
        self._agent_wallet = None
        
        # Initialize wallet manager
        self.wallet_manager = WalletManager("https://web3-agent.onrender.com")

    def set_agent_wallet(self, wallet: str):
        """Set agent wallet address - called by CTO Manager"""
        self._agent_wallet = wallet
        logger.info(f"Agent wallet set to: {wallet}")

    async def check_eligibility(self, wallet_address: str) -> Tuple[bool, str]:
        """Check if wallet meets challenge requirements"""
        if self._challenge_count < 2:
            return True, "No requirements for first challenge"
            
        try:
            if self._challenge_count == 2:
                required_percentage = self._base_token_percentage  # 0.5%
                required_transfer = self._base_transfer_amount    # 0.01 SOL
            elif self._challenge_count == 3:
                required_percentage = Decimal('1.0')  # 1.0%
                required_transfer = Decimal('0.1')    # 0.1 SOL
            else:
                required_percentage = Decimal('1.0') + (Decimal('0.1') * (self._challenge_count - 3))
                required_transfer = Decimal('0.2') * (2 ** (self._challenge_count - 4))
            
            # Mock API calls for now
            token_percentage = await self._mock_get_token_percentage(wallet_address)
            transfer_amount = await self._mock_get_transfer_amount(wallet_address)
            
            if token_percentage < required_percentage:
                return False, f"Wallet must hold at least {required_percentage}% of tokens"
                
            if transfer_amount < required_transfer:
                return False, f"Wallet must have transferred at least {required_transfer} SOL to agent"
                
            return True, "Eligible"
            
        except Exception as e:
            logger.error(f"Error checking eligibility: {e}")
            return False, "Error checking eligibility"

    async def _mock_get_token_percentage(self, wallet_address: str) -> Decimal:
        """Mock API call - replace with actual implementation"""
        # For testing, return 1% for specific test wallets
        if wallet_address == "D52HHAstwZ3v7uJptAusjJXEL2kv9jB5bidoQRMibTFD":
            return Decimal('1.0')
        return Decimal('0.0')

    async def _mock_get_transfer_amount(self, wallet_address: str) -> Decimal:
        """Mock API call - replace with actual implementation"""
        # For testing, return 0.1 SOL for specific test wallets
        if wallet_address == "D52HHAstwZ3v7uJptAusjJXEL2kv9jB5bidoQRMibTFD":
            return Decimal('0.1')
        return Decimal('0.0')

    def trigger_challenge(self) -> bool:
        """
        Trigger new challenge - called by CTO Manager
        Returns: Whether challenge was triggered successfully
        """
        # Double reward for next challenge (after first challenge)
        if self._challenge_count > 0:
            self._current_reward *= 2
            
        # Increment challenge count
        self._challenge_count += 1
        
        # Start the challenge
        success = self.start_challenge()
        if success:
            logger.info(f"Challenge {self._challenge_count} triggered with reward {self._current_reward} SOL")
        return success

    def generate_challenge_announcement(self) -> str:
        """Generate announcement for new challenge"""
        if self._challenge_count == 1:
            # First challenge - simple announcement
            return (
                "hewwo fwiends!! time for another numbow chawwenge! >w< "
                f"can u guess the numbow between {self._min_range} and {self._max_range}?? "
                f"the winnow gets {self._current_reward} SOL!! ^-^"
            )
        else:
            # Subsequent challenges - include requirements
            if self._challenge_count == 2:
                required_percentage = self._base_token_percentage  # 0.5%
                required_transfer = self._base_transfer_amount    # 0.01 SOL
            elif self._challenge_count == 3:
                required_percentage = Decimal('1.0')  # 1.0%
                required_transfer = Decimal('0.1')    # 0.1 SOL
            else:
                # After challenge 3
                required_percentage = Decimal('1.0') + (Decimal('0.1') * (self._challenge_count - 3))
                required_transfer = Decimal('0.2') * (2 ** (self._challenge_count - 4))  # 0.2, 0.4, 0.8...
            
            return (
                "OwO time for a speciaw chawwenge! >w< "
                f"can u guess the numbow between {self._min_range} and {self._max_range}?? "
                f"the winnow gets {self._current_reward} SOL!! "
                "\n\nbut wait!! to participate u need:\n"
                f"- howd at weast {required_percentage}% of ouw tokens in ur wawwet\n"
                f"- have twansfewwed {required_transfer} SOL to agent wawwet: {self._agent_wallet}\n\n"
                "good wuck fwiends!! ^-^"
            )

    async def check_guess(self, message: str, username: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Modified to check eligibility before processing guess
        """
        if not self._challenge_active or self._challenge_winner:
            return False, None, None

        wallet_address = self.extract_solana_wallet(message)
        if not wallet_address:
            return False, None, None

        # Check eligibility
        is_eligible, reason = await self.check_eligibility(wallet_address)
        if not is_eligible:
            return False, f"sowwy, but {reason}! >.<", wallet_address

        # Rest of the existing check_guess logic...
        numbers = re.findall(r'\d+', message)
        if not numbers:
            return False, "hmm i dont see any numbews in ur message! twy again! :3", wallet_address

        guess = int(numbers[0])
        
        if guess == self._current_number:
            success, tx_signature = self.notify_winner(wallet_address)
            
            if success and tx_signature:
                self._challenge_winner = username
                self._challenge_active = False
                
                response = (
                    f"YAYYY!! @{username} found the wight numbew ({self._current_number})!! "
                    f"{self._current_reward} SOL has been sent to ur wawwet! "
                    f"check the pinned message i wiww post in the nex few minutes for ur twansaction detaiws! "
                    f"stay tuned for the next chawwenge in the coming houws! ^w^"
                )
            else:
                response = "OMG u found the wight numbew but something went wong with the pwize! pwease contact suppowt! >.<"
                
            return True, response, wallet_address
        else:
            response = "sowwy, that's not the wight numbew! keep twying! >w<"
            return False, response, wallet_address

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

    def notify_winner(self, wallet_address: str) -> Tuple[bool, Optional[str]]:
        """
        Notify external service about winner and get transaction signature
        Returns: (success, transaction_signature)
        """
        try:
            # Get stored wallet credentials from wallet_credentials.json
            creds = self.wallet_manager.get_wallet_credentials()
            if not creds.get('private_key') or not creds.get('public_key'):
                logger.error("No wallet credentials found")
                return False, None
            
            payload = {
                "fromPrivateKey": creds['private_key'],
                "fromPublicKey": creds['public_key'],
                "toAddress": wallet_address,
                "amount": 0.1,  # Challenge reward amount
                "username": "twitter_winner",
                "challengeCompleted": True
            }
            
            logger.info(f"Sending reward to winner: {wallet_address}")
            response = requests.post(
                "https://web3-agent.onrender.com/trigger",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    tx_signature = data.get('signature')
                    if tx_signature:
                        logger.info(f"Successfully sent reward to winner: {wallet_address}")
                        logger.info(f"Transaction signature: {tx_signature}")
                        return True, tx_signature
                
                logger.error(f"API error: {data.get('message', 'Unknown error')}")
                
            logger.error(f"Failed to send reward. Status code: {response.status_code}")
            if response.text:
                logger.error(f"Response body: {response.text[:200]}")
            return False, None
            
        except Exception as e:
            logger.error(f"Error sending reward: {e}")
            return False, None

    def generate_winner_announcement(self, username: str, winning_number: int, tx_signature: str) -> str:
        """Generate announcement tweet for winner"""
        return (
            f"congwatuwations @{username} for winning the chawwenge!! "
            f"they found the wight numbew ({winning_number}) and won 0.1 SOL!! "
            f"hewe's the twansaction: https://solscan.io/tx/{tx_signature} ^w^"
        )