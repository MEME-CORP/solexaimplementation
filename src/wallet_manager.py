import os
import json
import logging
import requests
import time
from typing import Optional, Tuple, Dict, List
from pathlib import Path
from decimal import Decimal
import aiohttp  # Add to imports

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WalletManager')

class WalletManager:
    def __init__(self, api_url: str = "https://web3-agent.onrender.com"):
        """Initialize WalletManager with API URL"""
        self.api_url = api_url
        self.data_dir = Path("data")
        self.wallet_file = self.data_dir / "wallet_credentials.json"
        self.request_timeout = 30  # Default timeout in seconds
        
        # Create data directory if it doesn't exist
        self.data_dir.mkdir(exist_ok=True)
        
        # Load or create wallet credentials
        self.wallet_credentials = self._load_wallet_credentials()

    def generate_new_wallet(self) -> Tuple[bool, Optional[dict]]:
        """Generate a new wallet using the API"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating wallet (attempt {attempt + 1}/{max_retries})...")
                
                response = requests.post(
                    f"{self.api_url}/generate-wallet",
                    headers={"Content-Type": "application/json"},
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success' and data.get('wallet'):
                        wallet_data = data['wallet']
                        if all(k in wallet_data for k in ['publicKey', 'privateKey']):
                            logger.info(f"Successfully generated wallet: {wallet_data['publicKey']}")
                            return True, wallet_data
                        logger.error("Wallet data missing required keys")
                
                elif response.status_code == 502:
                    logger.warning(f"Server error (502) on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                        continue
                
                logger.error(f"API request failed with status {response.status_code}")
                if response.text:
                    logger.error(f"Response body: {response.text[:200]}")
                
            except requests.Timeout:
                logger.error(f"Request timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                    
            except requests.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                    
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return False, None
                
        return False, None

    def transfer_sol(self, from_wallet: str, to_wallet: str, amount: Decimal) -> Tuple[bool, Optional[str]]:
        """Transfer SOL from one wallet to another"""
        try:
            if amount <= Decimal('0'):
                raise ValueError("Amount must be greater than 0")
                
            creds = self.get_wallet_credentials()
            if not creds.get('private_key') or not creds.get('public_key'):
                raise ValueError("No wallet credentials found")

            payload = {
                "fromPrivateKey": creds['private_key'],
                "fromPublicKey": from_wallet,
                "toAddress": to_wallet,
                "amount": float(amount)  # Convert Decimal to float for JSON
            }
            
            response = requests.post(
                f"{self.api_url}/trigger",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    logger.info(f"Successfully transferred {amount} SOL to {to_wallet}")
                    return True, data.get('signature')
                logger.error(f"API error: {data.get('message')}")
            else:
                logger.error(f"Transfer failed with status {response.status_code}")
                if response.text:
                    logger.error(f"Response: {response.text[:200]}")
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Error in transfer_sol: {str(e)}")
            return False, None

    async def check_balance(self, wallet_address: str, mint_address: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        """Check wallet balance for both SOL and tokens"""
        try:
            payload = {
                "publicKey": wallet_address,
                "mintAddress": mint_address
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/check-balance",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.request_timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'success':
                            result = {
                                'sol': {
                                    'balance': Decimal(str(data['solBalance']['balance'])),
                                    'lamports': data['solBalance']['lamports']
                                }
                            }
                            
                            if data.get('tokenBalance') and not data['tokenBalance'].get('error'):
                                result['token'] = {
                                    'balance': Decimal(str(data['tokenBalance']['balance'])),
                                    'decimals': data['tokenBalance']['decimals'],
                                    'mint': data['tokenBalance']['mint']
                                }
                                
                            return True, result
                            
                    logger.error(f"Balance check failed: {response.status}")
                    return False, None
                    
        except Exception as e:
            logger.error(f"Error checking balance: {str(e)}")
            return False, None

    def check_mint_balance(self, mint_address: str) -> Tuple[bool, Optional[Dict]]:
        """Check mint balance and supply information"""
        try:
            response = requests.post(
                f"{self.api_url}/check-mint-balance",
                json={"mintAddress": mint_address},
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return True, {
                        'balance': Decimal(str(data['balance'])),
                        'decimals': data['decimals'],
                        'rawAmount': data['rawAmount']
                    }
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking mint balance: {str(e)}")
            return False, None

    def check_transfers(self, from_address: str, to_address: str, 
                       before_time: Optional[int] = None, 
                       after_time: Optional[int] = None) -> Tuple[bool, Optional[List]]:
        """Check transfer history between wallets"""
        try:
            payload = {
                "fromAddress": from_address,
                "toAddress": to_address,
                "beforeTime": before_time,
                "afterTime": after_time
            }
            
            response = requests.post(
                f"{self.api_url}/check-transfers",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return True, data.get('transfers', [])
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking transfers: {str(e)}")
            return False, None

    def get_holder_percentage(self, mint_address: str, holder_address: str) -> Tuple[bool, Optional[Dict]]:
        """Get holder's percentage of total supply"""
        try:
            payload = {
                "mintAddress": mint_address,
                "holderAddress": holder_address
            }
            
            response = requests.post(
                f"{self.api_url}/holder-percentage",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return True, data.get('data')
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Error getting holder percentage: {str(e)}")
            return False, None

    def burn_tokens(self, from_private_key: str, from_public_key: str,
                   mint_address: str, amount: Decimal, decimals: int) -> Tuple[bool, Optional[str]]:
        """Burn tokens from a wallet"""
        try:
            payload = {
                "fromPrivateKey": from_private_key,
                "fromPublicKey": from_public_key,
                "mintAddress": mint_address,
                "amount": float(amount),
                "decimals": decimals
            }
            
            response = requests.post(
                f"{self.api_url}/burn-tokens",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return True, data.get('signature')
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Error burning tokens: {str(e)}")
            return False, None

    def buy_tokens(self, private_key: str, token_address: str, 
                  amount_usd: Decimal = Decimal('0.1')) -> Tuple[bool, Optional[Dict]]:
        """Buy tokens using Jupiter swap"""
        try:
            payload = {
                "privateKey": private_key,
                "tokenAddress": token_address,
                "amountUSD": float(amount_usd)
            }
            
            response = requests.post(
                f"{self.api_url}/buy-tokens",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return True, data.get('data')
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Error buying tokens: {str(e)}")
            return False, None

    # Keep existing helper methods
    def _load_wallet_credentials(self) -> dict:
        """Load wallet credentials from file"""
        try:
            if self.wallet_file.exists():
                with open(self.wallet_file, 'r') as f:
                    return json.load(f)
            else:
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
        """Save wallet credentials to file"""
        try:
            with open(self.wallet_file, 'w') as f:
                json.dump(self.wallet_credentials, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving wallet credentials: {e}")
            return False

    def set_wallet_credentials(self, public_key: str, private_key: str, secret_key: str) -> bool:
        """Set wallet credentials"""
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