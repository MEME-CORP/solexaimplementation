import os
import json
import logging
import requests
from typing import Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WalletManager')

class WalletManager:
    def __init__(self, api_url: str = "http://localhost:3000"):
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
            payload = {
                "username": username,
                "challengeCompleted": True,
                "solanaAddress": wallet_address
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