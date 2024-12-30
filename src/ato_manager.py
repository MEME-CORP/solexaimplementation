import logging
import asyncio
import time
from decimal import Decimal
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta
from src.wallet_manager import WalletManager
from src.config import Config
from src.announcement_broadcaster import AnnouncementBroadcaster
from src.memory_processor import MemoryProcessor
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ATOManager')

class ATOManager:
    def __init__(self):
        """Initialize ATO Manager"""
        self.wallet_manager = WalletManager()
        self.broadcaster = AnnouncementBroadcaster()
        self.memory_processor = MemoryProcessor()
        self._agent_wallet = None
        self._token_mint = Config.TOKEN_MINT_ADDRESS
        self._current_milestone_index = 0
        self._max_retries = 3
        self._retry_delay = 2
        
        # Initial milestones up to 1M
        self._base_milestones = [
            (Decimal('75000'), Decimal('0.5'), Decimal('0.2')),  # (mc, burn%, sol_buyback)
            (Decimal('150000'), Decimal('0.5'), Decimal('0.4')),
            (Decimal('300000'), Decimal('0.5'), Decimal('0.8')),
            (Decimal('600000'), Decimal('0.5'), Decimal('1.0')),
            (Decimal('1000000'), Decimal('0.5'), Decimal('1.5'))  # Special case - split burn
        ]
        
        # Generate extended milestones beyond 1M
        self._milestones = self._generate_extended_milestones()
        
        self._total_supply = Decimal('1000000000')  # 1 billion tokens

    def _generate_extended_milestones(self) -> List[Tuple[Decimal, Decimal, Decimal]]:
        """Generate all milestones including beyond 1M"""
        milestones = self._base_milestones.copy()
        
        current_mc = Decimal('1000000')
        current_buyback = Decimal('1.5')
        
        while current_mc <= Decimal('10000000'):
            current_mc *= 2
            current_buyback += Decimal('0.5')
            milestones.append((current_mc, Decimal('0.5'), current_buyback))
            
        # Add milestones beyond 10M
        while current_mc <= Decimal('100000000'):  # Cap at 100M for now
            current_mc *= 2
            current_buyback += Decimal('0.5')
            milestones.append((current_mc, Decimal('0.5'), current_buyback))
            
        return milestones

    async def initialize(self):
        """Initialize agent wallet and start monitoring"""
        # Check if we already have wallet credentials
        existing_credentials = self.wallet_manager.get_wallet_credentials()
        if existing_credentials and existing_credentials.get('public_key'):
            logger.info("Using existing wallet credentials")
            self._agent_wallet = existing_credentials['public_key']
            self._post_wallet_announcement()
            
            # Start token monitoring
            await self._start_token_monitoring()
            return True
        
        # If no existing credentials, generate new wallet
        success, wallet_data = self.wallet_manager.generate_new_wallet()
        if not success:
            logger.error("Failed to generate agent wallet")
            return False
        
        # Store the credentials properly
        if not self.wallet_manager.set_wallet_credentials(
            public_key=wallet_data['publicKey'],
            private_key=wallet_data['privateKey'],
            secret_key=wallet_data['privateKey']  # Using private key as secret key
        ):
            logger.error("Failed to store wallet credentials")
            return False
            
        self._agent_wallet = wallet_data['publicKey']
        self._post_wallet_announcement()
        
        # Start token monitoring
        await self._start_token_monitoring()
        return True
        
    def _store_announcement_memory(self, announcement: str):
        """Helper method to store announcements as memories"""
        try:
            # Use synchronous storage
            success = self.memory_processor.store_announcement_sync(announcement)
            if success:
                logger.info("Stored announcement in memories")
            else:
                logger.error("Failed to store announcement")
        except Exception as e:
            logger.error(f"Error storing announcement memory: {e}")
            
    def _post_wallet_announcement(self):
        """Post wallet announcement in character style"""
        announcement = (
            "hewwo fwiends!! >w< \n\n"
            f"i just cweated my speciaw agent wawwet: {self._agent_wallet}\n\n"
            "mr dev, pwease send the tokens hewe so we can stawt the Agent Take Ovew (ATO)!\n"
            "i'ww make suwe to pump this waunch to the moon! uwu\n\n"
            "waiting fow tokens..."
        )
        logger.info(f"Posted wallet announcement: {announcement}")
        
        # Use create_task for broadcasting but store memory synchronously
        asyncio.create_task(self.broadcaster.broadcast(announcement))
        self._store_announcement_memory(announcement)  # Direct call, no create_task
        return announcement
        
    async def _start_token_monitoring(self):
        """Monitor token balance until tokens are received"""
        try:
            check_count = 0
            logger.info("Starting token balance monitoring...")
            
            while True:
                balance = await self._check_token_balance()
                logger.info(f"Current token balance: {balance}")
                
                if balance > 0:
                    logger.info(f"Tokens received! Balance: {balance}")
                    # Create announcement task
                    announcement_task = asyncio.create_task(self._handle_token_receipt(balance))
                    
                    try:
                        # Wait for the announcement and post-receipt actions to complete
                        await announcement_task
                    except Exception as e:
                        logger.error(f"Error in token receipt handling: {e}")
                    break
                
                # Break after a few checks in test environment
                check_count += 1
                if 'pytest' in sys.modules or 'unittest' in sys.modules:
                    if check_count >= 2:
                        break
                
                logger.info("No tokens yet, waiting before next check...")
                await asyncio.sleep(1 if 'pytest' in sys.modules or 'unittest' in sys.modules else 120)
                
        except Exception as e:
            logger.error(f"Error in token monitoring: {e}")

    async def _handle_token_receipt(self, balance: Decimal):
        """Handle token receipt announcement and post-receipt actions"""
        try:
            # Post announcement first
            announcement = self._post_tokens_received(balance)
            
            # Ensure the broadcast completes
            if hasattr(self, '_broadcast_tasks') and self._broadcast_tasks:
                await asyncio.gather(*self._broadcast_tasks)
                self._broadcast_tasks.clear()
            
            # Then activate post-receipt actions
            await self._activate_post_token_receipt()
            
        except Exception as e:
            logger.error(f"Error handling token receipt: {e}")
            raise

    async def _check_token_balance(self) -> Decimal:
        """Check token balance using new /check-balance endpoint"""
        for attempt in range(self._max_retries):
            try:
                success, balance_data = await self.wallet_manager.check_balance(
                    self._agent_wallet,
                    self._token_mint
                )
                
                if success and balance_data:
                    # Check if token balance exists and has a balance field
                    if 'token' in balance_data and 'balance' in balance_data['token']:
                        balance = balance_data['token']['balance']
                        logger.info(f"Token balance check successful: {balance}")
                        return balance
                    else:
                        logger.info("No token balance found")
                        
                logger.warning(f"Balance check attempt {attempt + 1} failed")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    
            except Exception as e:
                logger.error(f"Error checking token balance: {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    
        return Decimal('0')

    async def _check_sol_balance(self) -> Decimal:
        """Check SOL balance using new /check-balance endpoint"""
        try:
            success, balance_data = await self.wallet_manager.check_balance(self._agent_wallet)
            if success and balance_data and 'sol' in balance_data:
                return balance_data['sol']['balance']
            return Decimal('0')
        except Exception as e:
            logger.error(f"Error checking SOL balance: {e}")
            return Decimal('0')

    async def _transfer_sol(self, to_address: str, amount: Decimal) -> bool:
        """Transfer SOL using new /trigger endpoint"""
        try:
            if amount <= Decimal('0'):
                raise ValueError("Transfer amount must be greater than 0")
                
            success, signature = await self.wallet_manager.transfer_sol(
                self._agent_wallet,
                to_address,
                amount
            )
            
            if success and signature:
                logger.info(f"Successfully transferred {amount} SOL to {to_address}")
                logger.info(f"Transaction: {signature}")
                return True
                
            logger.error("Transfer failed")
            return False
            
        except Exception as e:
            logger.error(f"Error transferring SOL: {e}")
            return False

    async def _transfer_tokens(self, to_address: str, amount: Decimal) -> bool:
        """Transfer tokens using updated format"""
        try:
            if amount <= Decimal('0'):
                raise ValueError("Transfer amount must be greater than 0")
                
            success, signature = await self.wallet_manager.transfer_sol(
                self._agent_wallet,
                to_address,
                amount,
                self._token_mint
            )
            
            if success and signature:
                logger.info(f"Successfully transferred {amount} tokens to {to_address}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error transferring tokens: {e}")
            return False

    async def _burn_tokens(self, amount: Decimal) -> bool:
        """Burn tokens using new /burn-tokens endpoint"""
        try:
            if amount <= Decimal('0'):
                raise ValueError("Burn amount must be greater than 0")
                
            creds = self.wallet_manager.get_wallet_credentials()
            success, signature = await self.wallet_manager.burn_tokens(
                creds['private_key'],
                self._agent_wallet,
                self._token_mint,
                amount,
                9  # Token decimals
            )
            
            if success and signature:
                logger.info(f"Successfully burned {amount} tokens")
                logger.info(f"Transaction: {signature}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error burning tokens: {e}")
            return False

    async def _execute_buyback(self, sol_amount: Decimal) -> bool:
        """Execute buyback using new /buy-tokens endpoint"""
        try:
            if sol_amount <= Decimal('0'):
                raise ValueError("Buyback amount must be greater than 0")
                
            creds = self.wallet_manager.get_wallet_credentials()
            success, data = await self.wallet_manager.buy_tokens(
                creds['private_key'],
                self._token_mint,
                sol_amount
            )
            
            if success and data:
                logger.info(f"Successfully executed buyback for {sol_amount} SOL")
                logger.info(f"Transaction: {data['transactionId']}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error executing buyback: {e}")
            return False

    async def check_holder_percentage(self, holder_address: str) -> Tuple[bool, Optional[Decimal]]:
        """Check holder's percentage of total supply"""
        try:
            success, data = await self.wallet_manager.get_holder_percentage(
                self._token_mint,
                holder_address
            )
            
            if success and data:
                return True, Decimal(str(data['percentage']))
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking holder percentage: {e}")
            return False, None

    async def check_mint_supply(self) -> Tuple[bool, Optional[Dict]]:
        """Check current mint supply information"""
        try:
            success, data = await self.wallet_manager.check_mint_balance(self._token_mint)
            if success and data:
                return True, data
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking mint supply: {e}")
            return False, None

    async def verify_transfers(self, from_address: str, min_amount: Decimal) -> bool:
        """Verify transfer requirements are met"""
        try:
            success, transfers = await self.wallet_manager.check_transfers(
                from_address,
                self._agent_wallet
            )
            
            if not success or not transfers:
                return False
                
            total_transferred = Decimal('0')
            for tx in transfers:
                if tx.get('status') == 'success':
                    total_transferred += Decimal(str(tx['amount'])) / Decimal('1000000000')
                    
            return total_transferred >= min_amount
            
        except Exception as e:
            logger.error(f"Error verifying transfers: {e}")
            return False

    async def _check_marketcap(self) -> Decimal:
        """Check current marketcap of token"""
        try:
            success, marketcap = await self.wallet_manager.get_token_marketcap(self._token_mint)
            if success and marketcap is not None:
                logger.info(f"Retrieved marketcap: {marketcap}")
                return marketcap
            logger.warning("Failed to get marketcap data")
            return Decimal('0')
        except Exception as e:
            logger.error(f"Error checking marketcap: {e}")
            return Decimal('0')
            
    def _format_announcement_for_twitter(self, announcement: str) -> str:
        """Format announcement to fit Twitter's character limit"""
        # Twitter's character limit is 280
        if len(announcement) <= 280:
            return announcement
            
        # If longer, try to find a good breaking point
        shortened = announcement[:277] + "..."
        return shortened

    def _post_tokens_received(self, balance: Decimal):
        """Post announcement when tokens are received"""
        announcement = (
            f"nyaa~! tokens received!! {balance} tokens awe now in my wawwet! >w<\n\n"
            "thank u mr dev! now i can stawt the Agent Take Ovew!\n"
            "wet's make this waunch go to the mooooon! uwu\n\n"            
        )
        logger.info(f"Posted tokens received: {announcement}")
        
        # Single broadcast task
        asyncio.create_task(self.broadcaster.broadcast(announcement))
        
        # Store memory synchronously
        try:
            self._store_announcement_memory(announcement)
        except Exception as e:
            logger.error(f"Error storing announcement memory: {e}")
        
        return announcement

    async def _activate_post_token_receipt(self):
        """Handle actions after tokens are received"""
        try:
            # Get initial marketcap and post milestones
            initial_mc = await self._check_marketcap()
            
            # Single broadcast for milestone announcement
            await self.broadcaster.broadcast(self._post_milestone_announcement(initial_mc))
            
            # Start marketcap monitoring
            await self._monitor_marketcap()
            
        except Exception as e:
            logger.error(f"Error in post-token receipt activation: {e}")
            raise

    async def _execute_standard_milestone(self, burn_percentage: Decimal, buyback_amount: Decimal):
        """Execute standard milestone"""
        try:
            # Execute burn
            burn_success = await self._burn_tokens(burn_percentage)
            
            # Execute buyback
            buyback_success = await self._execute_buyback(buyback_amount)
            
            announcement = (
                f"miwestone weached! time to dewiver! >w<\n"
                f"- {'✅' if burn_success else '❌'} burning {burn_percentage}% of suppwy\n"
                f"- {'✅' if buyback_success else '❌'} making {buyback_amount} SOL buyback!\n\n"
                "wet's keep pushing! uwu"
            )
            logger.info(announcement)
            return announcement
            
        except Exception as e:
            logger.error(f"Error in milestone execution: {e}")
            return "oopsie! something went wong with the miwestone! >.<"
            
    async def _execute_special_milestone(self, burn_percentage: Decimal, buyback_amount: Decimal):
        """Execute special milestone with dev reward"""
        try:
            # Calculate amounts
            half_burn = burn_percentage / 2
            
            # Execute burn
            burn_success = await self._burn_tokens(half_burn)
            
            # Transfer to dev
            dev_success = await self._transfer_tokens(
                Config.DEV_WALLET_ADDRESS,  # Assuming this exists in Config
                (self._total_supply * half_burn) / Decimal('100')
            )
            
            # Execute buyback
            buyback_success = await self._execute_buyback(buyback_amount)
            
            announcement = (
                f"nyaa~! speciaw miwestone weached! >w<\n"
                f"- {'✅' if burn_success else '❌'} burning {half_burn}% of suppwy\n"
                f"- {'✅' if dev_success else '❌'} sending {half_burn}% to dev\n"
                f"- {'✅' if buyback_success else '❌'} making {buyback_amount} SOL buyback!\n\n"
                "good job evewyone! uwu"
            )
            logger.info(announcement)
            return announcement
            
        except Exception as e:
            logger.error(f"Error in special milestone execution: {e}")
            return "oopsie! something went wong with the speciaw miwestone! >.<"

    def _post_milestone_announcement(self, current_mc: Decimal):
        """Post milestone targets announcement"""
        def format_milestone(mc: Decimal, burn: Decimal, buyback: Decimal) -> str:
            mc_k = mc / 1000
            return f"- {mc_k}k mc: burn {burn}% + {buyback} SOL buyback!"

        milestones_text = "\n".join([
            format_milestone(mc, burn, buyback) 
            for mc, burn, buyback in self._milestones[:5]  # First 5 milestones
        ])

        announcement = (
            f"current marketcap: {current_mc/1000}k! here's our pwan! >w<\n\n"
            f"{milestones_text}\n\n"
            "uwu"
        )
        logger.info(f"Posted milestones: {announcement}")
        
        # Format for Twitter
        twitter_announcement = self._format_announcement_for_twitter(announcement)
        
        # Single broadcast
        return twitter_announcement

    async def _monitor_marketcap(self):
        """Monitor marketcap and handle milestones"""
        try:
            while True:
                current_mc = await self._check_marketcap()
                
                # Check if we've hit the next milestone
                if self._current_milestone_index < len(self._milestones):
                    next_milestone = self._milestones[self._current_milestone_index]
                    if current_mc >= next_milestone[0]:
                        await self._handle_milestone_reached(current_mc)
                
                # Post current marketcap update
                self._post_marketcap_update(current_mc)
                
                await asyncio.sleep(1200)  # Check every 20 minutes
        except Exception as e:
            logger.error(f"Error in marketcap monitoring: {e}")

    async def _handle_milestone_reached(self, current_mc: Decimal):
        """Handle reached milestone"""
        milestone = self._milestones[self._current_milestone_index]
        mc, burn_percentage, buyback_amount = milestone
        
        # Special cases for 1M and 10M
        if mc == Decimal('1000000') or mc == Decimal('10000000'):
            await self._execute_special_milestone(burn_percentage, buyback_amount)
        else:
            await self._execute_standard_milestone(burn_percentage, buyback_amount)
        
        self._current_milestone_index += 1

    def _post_marketcap_update(self, current_mc: Decimal):
        """Post regular marketcap update"""
        if self._current_milestone_index < len(self._milestones):
            next_milestone = self._milestones[self._current_milestone_index]
            remaining = next_milestone[0] - current_mc
            
            announcement = (
                f"current marketcap: {current_mc/1000}k! >w<\n"
                f"next miwestone: {next_milestone[0]/1000}k\n"
                f"remaining: {remaining/1000}k to go!\n"
                "*tail wags with excitement*"
            )
        else:
            announcement = (
                f"current marketcap: {current_mc/1000}k! >w<\n"
                "we've hit all our miwestones! amazing job! uwu"
            )
            
        logger.info(f"Posted marketcap update: {announcement}")
        
        # Format for Twitter
        twitter_announcement = self._format_announcement_for_twitter(announcement)
        
        # Single broadcast
        asyncio.create_task(self.broadcaster.broadcast(twitter_announcement))
        return announcement