import os
import json
import logging
import requests
import time
from typing import Optional, Tuple
from pathlib import Path
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WalletManager')

class WalletManager:
    def __init__(self, api_url: str = "https://web3-agent.onrender.com"):
        """
        Initialize WalletManager with API URL
        Args:
            api_url: URL of the Solana wallet API service
        """
        self.api_url = api_url
        self.data_dir = Path("data")
        self.wallet_file = self.data_dir / "wallet_credentials.json"
        
        # Create data directory if it doesn't exist
        self.data_dir.mkdir(exist_ok=True)
        
        # Load or create wallet credentials
        self.wallet_credentials = self._load_wallet_credentials()
        
    def _load_wallet_credentials(self) -> dict:
        """
        Load wallet credentials from file or create new ones
        Returns:
            dict: Wallet credentials
        """
        try:
            if self.wallet_file.exists():
                with open(self.wallet_file, 'r') as f:
                    return json.load(f)
            else:
                # Initialize empty credentials
                credentials = {
                    "public_key": None,
                    "private_key": None,
                    "secret_key": None
                }
                with open(self.wallet_file, 'w') as f:
                    json.dump(credentials, f, indent=4)
                return credentials
                
        except Exception as e:
            logger.error(f"Error loading wallet credentials: {e}")
            return {}

    def _save_wallet_credentials(self) -> bool:
        """
        Save wallet credentials to file
        Returns:
            bool: Success status
        """
        try:
            with open(self.wallet_file, 'w') as f:
                json.dump(self.wallet_credentials, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving wallet credentials: {e}")
            return False

    def set_wallet_credentials(self, public_key: str, private_key: str, secret_key: str) -> bool:
        """
        Set wallet credentials
        Args:
            public_key: Wallet public key
            private_key: Wallet private key
            secret_key: Wallet secret key
        Returns:
            bool: Success status
        """
        try:
            self.wallet_credentials = {
                "public_key": public_key,
                "private_key": private_key,
                "secret_key": secret_key
            }
            return self._save_wallet_credentials()
        except Exception as e:
            logger.error(f"Error setting wallet credentials: {e}")
            return False

    def get_wallet_credentials(self) -> dict:
        """Get stored wallet credentials"""
        return self.wallet_credentials

    def generate_new_wallet(self) -> Tuple[bool, Optional[dict]]:
        """
        Generate a new wallet using the API
        Returns:
            Tuple[bool, dict]: (success, wallet_data)
        """
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating wallet (attempt {attempt + 1}/{max_retries})...")
                
                response = requests.post(
                    f"{self.api_url}/generate-wallet",
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                # Log response details for debugging
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response headers: {response.headers}")
                
                if response.status_code == 200:
                    data = response.json()
                    # Temporarily log the structure (not the actual values)
                    logger.debug(f"Response data keys: {data.keys()}")
                    if 'wallet' in data:
                        logger.debug(f"Wallet data keys: {data['wallet'].keys()}")
                    
                    if data.get('status') == 'success' and data.get('wallet'):
                        wallet_data = data.get('wallet')
                        # Verify we have both required keys
                        if 'publicKey' in wallet_data and 'privateKey' in wallet_data:
                            logger.info("Successfully generated wallet with both public and private keys")
                            # Never log the actual private key!
                            logger.info(f"Public key received: {wallet_data['publicKey']}")
                            return True, wallet_data
                        else:
                            logger.error("Wallet data missing required keys")
                            logger.debug(f"Available keys: {wallet_data.keys()}")
                    else:
                        logger.error(f"API returned success but invalid data: {data}")
                        
                elif response.status_code == 502:
                    logger.warning(f"Server error (502) on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                        
                logger.error(f"API request failed with status {response.status_code}")
                if response.text:
                    logger.error(f"Response body: {response.text[:200]}")
                    
                return False, None
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return False, None
            
            except Exception as e:
                logger.error(f"Unexpected error generating wallet: {str(e)}")
                return False, None
                
        logger.error("Failed to generate wallet after all retries")
        return False, None

    def send_reward(self, username: str, wallet_address: str) -> Tuple[bool, Optional[str]]:
        """
        Send SOL reward to winner's wallet address
        Args:
            username: Winner's username
            wallet_address: Winner's Solana wallet address
        Returns:
            Tuple[bool, Optional[str]]: (success, transaction_signature)
        """
        try:
            # Get stored wallet credentials
            creds = self.get_wallet_credentials()
            if not creds.get('private_key') or not creds.get('public_key'):
                logger.error("No wallet credentials found")
                return False, None

            payload = {
                "fromPrivateKey": creds['private_key'],
                "fromPublicKey": creds['public_key'],
                "toAddress": wallet_address,
                "amount": 0.001,  # Default reward amount
                "username": username,
                "challengeCompleted": True
            }
            
            response = requests.post(
                f"{self.api_url}/trigger",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info(f"Successfully sent reward to {username} ({wallet_address})")
                    return True, data.get('signature')
                else:
                    logger.error(f"API error: {data.get('message')}")
                    return False, None
            else:
                logger.error(f"API request failed with status {response.status_code}")
                return False, None
            
        except Exception as e:
            logger.error(f"Error sending reward: {e}")
            return False, None

    def verify_wallet_address(self, wallet_address: str) -> bool:
        """
        Verify if a wallet address is valid
        Args:
            wallet_address: Solana wallet address to verify
        Returns:
            bool: Whether address is valid
        """
        # Basic validation - check length and characters
        if not wallet_address or len(wallet_address) != 44:
            return False
            
        # Check for valid Base58 characters (excluding 0, O, I, l)
        valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
        return all(c in valid_chars for c in wallet_address) 

    def check_balance(self, wallet_address: str) -> Tuple[bool, Optional[float], Optional[int]]:
        """
        Check wallet balance using the API
        Args:
            wallet_address: Solana wallet address to check
        Returns:
            Tuple[bool, Optional[float], Optional[int]]: (success, balance_in_sol, balance_in_lamports)
        """
        try:
            payload = {
                "publicKey": wallet_address
            }
            
            response = requests.post(
                f"{self.api_url}/check-balance",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info(f"Successfully retrieved balance for {wallet_address}")
                    return True, data.get('balance'), data.get('lamports')
                else:
                    logger.error(f"API error: {data.get('message')}")
                    return False, None, None
            else:
                logger.error(f"API request failed with status {response.status_code}")
                if response.text:
                    logger.error(f"Response body: {response.text[:200]}")
                return False, None, None
                
        except Exception as e:
            logger.error(f"Error checking balance: {str(e)}")
            return False, None, None

    async def check_token_balance(self, wallet_address: str, mint_address: str) -> Decimal:
        """
        Check token balance for a specific wallet and mint address
        For now this is a mock that will be replaced with actual API call
        """
        try:
            # TODO: Replace with actual API call
            # Example API endpoint would be:
            # GET /api/v1/token-balance?wallet={wallet_address}&mint={mint_address}
            
            # Mock implementation
            return Decimal('0')
            
        except Exception as e:
            logger.error(f"Error checking token balance: {e}")
            return Decimal('0')