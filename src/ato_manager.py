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
import json
from pathlib import Path
from src.prompts import load_style_prompts
from src.creativity_manager import CreativityManager
from src.ai_announcements import AIAnnouncements
from src.database.supabase_client import DatabaseService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ATOManager')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)

class ATOManager:
    def __init__(self):
        """Initialize ATO Manager"""
        # Add database initialization
        self.db = DatabaseService()
        
        # Add system prompt loading
        self.system_prompts = load_style_prompts()
        if not self.system_prompts or 'style1' not in self.system_prompts:
            logger.error("Failed to load system prompt")
            raise ValueError("System prompt configuration missing")
            
        self.system_prompt = self.system_prompts['style1']
        
        # Initialize AI announcements
        self.ai_announcements = AIAnnouncements()
        
        self.wallet_manager = WalletManager()
        self.broadcaster = AnnouncementBroadcaster()
        self.memory_processor = MemoryProcessor()
        self._agent_wallet = None
        self._token_mint = Config.TOKEN_MINT_ADDRESS
        self._current_milestone_index = 0
        self._max_retries = 3
        self._retry_delay = 2
        
        # Initial milestones up to 100M
        self._base_milestones = [
            (Decimal('75000'), Decimal('0.00000001'), Decimal('0.001')),  # (mc, burn%, sol_buyback)
            (Decimal('150000'), Decimal('0.0000001'), Decimal('0.001')),
            (Decimal('300000'), Decimal('0.000001'), Decimal('0.001')),
            (Decimal('600000'), Decimal('0.00001'), Decimal('0.001')),
            (Decimal('1000000'), Decimal('0.0001'), Decimal('0.001')),  # 1M milestone
            (Decimal('5000000'), Decimal('0.001'), Decimal('0.001')),          # 5M milestone
            (Decimal('10000000'), Decimal('0.01'), Decimal('0.001')),         # 10M milestone
            (Decimal('20000000'), Decimal('0.1'), Decimal('0.001')),         # 20M milestone
            (Decimal('50000000'), Decimal('1'), Decimal('0.001')),         # 50M milestone
            (Decimal('100000000'), Decimal('2'), Decimal('0.001'))         # 100M milestone
        ]
        
        # Generate extended milestones beyond 1M
        self._milestones = self._generate_extended_milestones()
        
        self._total_supply = Decimal('1000000000')  # 1 billion tokens
        
        # Add announcement tracking
        self._announcements_file = Path("data/announcements.json")
        self._announcements_file.parent.mkdir(parents=True, exist_ok=True)
        self._announcement_history = self._load_announcement_history()
        
        self.creativity_manager = CreativityManager()
        self.narrative = {}

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
        try:
            # Check if we already have wallet credentials
            existing_credentials = self.wallet_manager.get_wallet_credentials()
            if existing_credentials and existing_credentials.get('public_key'):
                logger.info("Using existing wallet credentials")
                self._agent_wallet = existing_credentials['public_key']
                
                # Only post wallet announcement if it hasn't been done before
                if not self._announcement_history.get('wallet_announced', False):
                    self._post_wallet_announcement()
                    # Update history to mark wallet as announced
                    self._announcement_history['wallet_announced'] = True
                    self._save_announcement_history()
                else:
                    logger.info("Wallet announcement already made, skipping...")
                
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
            
            # Post initial wallet announcement and mark as announced
            self._post_wallet_announcement()
            self._announcement_history['wallet_announced'] = True
            self._save_announcement_history()
            
            # Start token monitoring
            await self._start_token_monitoring()
            return True
            
        except Exception as e:
            logger.error(f"Error in initialize: {e}")
            return False
        
    def _store_announcement_memory(self, announcement: str) -> bool:
        """Helper method to store announcements as memories synchronously"""
        try:
            # Ensure announcement is properly formatted
            if not announcement or not announcement.strip():
                logger.error("Empty or invalid announcement")
                return False
            
            formatted_announcement = announcement.strip()
            
            # Use synchronous storage with proper memory format
            success = self.memory_processor.store_announcement_sync(formatted_announcement)
            
            if success:
                logger.info(f"Successfully stored announcement in memories: {formatted_announcement[:100]}...")
                return True
            else:
                logger.error("Failed to store announcement in database")
                return False
            
        except Exception as e:
            logger.error(f"Error storing announcement memory: {e}")
            logger.exception("Full traceback:")
            return False

    def _post_wallet_announcement(self):
        """Post wallet announcement in character style"""
        announcement = (
            "yo check dis wallet we just set up\n\n"
            f"dis our new operation base: {self._agent_wallet}\n\n"
            "we bout 2 run dis Agent Take Ovah (ATO) like a straight boss move\n"            
            "waitin on dem tokens 2 drop... we dont play"
        )
        logger.info(f"Posted wallet announcement: {announcement}")
        
        try:
            # Store memory synchronously first
            if not self._store_announcement_memory(announcement):
                logger.error("Failed to store announcement in database")
            
            # Then broadcast
            asyncio.create_task(self.broadcaster.broadcast(announcement))
            return announcement
        except Exception as e:
            logger.error(f"Error in wallet announcement: {e}")
            return None
        
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
                await asyncio.sleep(1 if 'pytest' in sys.modules or 'unittest' in sys.modules else 60)
                
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
                # Update creativity manager's cache
                self.creativity_manager.update_cached_market_data(marketcap)
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
        try:
            # Check if announcement was already made
            if self._announcement_history['tokens_received']:
                logger.info("Tokens received announcement was already made, skipping...")
                return None

            announcement = (
                f"familia we just received {balance} tokens\n\n"
                "dev team came thru wit da goods\n"
                "we bout 2 run this Agent Take Over (ATO) like real papayas\n\n"
                "whole operation's locked & loaded... watch us move"
            )
            
            # Store announcement synchronously
            storage_success = self._store_announcement_memory(announcement)
            if not storage_success:
                logger.error("Failed to store tokens received announcement")
            
            # Update history and save
            self._announcement_history['tokens_received'] = True
            self._save_announcement_history()
            
            # Create broadcast task
            asyncio.create_task(self.broadcaster.broadcast(announcement))
            
            return announcement
            
        except Exception as e:
            logger.error(f"Error in _post_tokens_received: {e}")
            return "Error posting tokens received announcement"

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
        """Execute standard milestone with improved burn verification"""
        try:
            # Add delay between operations
            await asyncio.sleep(10)  # Increased initial delay
            
            # Execute burn with verification
            burn_success = False
            burn_attempts = 3
            for attempt in range(burn_attempts):
                burn_success = await self._burn_tokens(burn_percentage)
                if burn_success:
                    break
                await asyncio.sleep(10 * (attempt + 1))  # Exponential backoff between attempts
            
            # Add longer delay between burn and buyback
            await asyncio.sleep(15)  # Increased from 10 to 15 seconds
            
            # Execute buyback (keeping existing logic as it works)
            buyback_success = await self._execute_buyback(buyback_amount)
            
            # Calculate burn amount by multiplying by 1000 and format to 5 decimal places
            burn_amount_display = f"{float(burn_percentage * 1000):.5f}"
            
            announcement = (
                f"we hit da milestone, no games\n"
                f"- Token Burn: {'we did it' if burn_success else 'missed'} {burn_amount_display} tokens gone\n"
                f"- Buyback: {'locked down' if buyback_success else 'failed'} {buyback_amount} SOL used for buyback\n\n"
                "operation continues... we dont stop"
            )
            logger.info(announcement)
            
            # Add broadcast task for the announcement
            await self.broadcaster.broadcast(announcement)
            
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
                f"special move activated, real talk\n"
                f"- Token Burn: {'executed' if burn_success else 'blocked'} - {half_burn}% supply dropped\n"
                f"- Dev Cut: {'transferred' if dev_success else 'intercepted'} - {half_burn}% 2 da team\n"
                f"- Buyback: {'secured' if buyback_success else 'interrupted'} - {buyback_amount} SOL in play\n\n"
                "strategic maneuver complete... we stay winning"
            )
            logger.info(announcement)
            
            # Add broadcast task for the announcement
            await self.broadcaster.broadcast(announcement)
            
            return announcement
            
        except Exception as e:
            logger.error(f"Error in special milestone execution: {e}")
            return "oopsie! something went wong with the speciaw miwestone! >.<"

    def _post_milestone_announcement(self, current_mc: Decimal):
        """Post milestone targets announcement"""
        # Check if announcement was already made
        if self._announcement_history['initial_milestones']:
            logger.info("Initial milestones announcement was already made, skipping...")
            return None
        
        def format_milestone(mc: Decimal, burn: Decimal, buyback: Decimal) -> str:
            # Use the same dot formatting for consistency
            mc_formatted = self._format_number_with_dots(int(mc))
            return f"- {mc_formatted}: burn {burn}% + {buyback} SOL buyback!"

        milestones_text = "\n".join([
            format_milestone(mc, burn, buyback) 
            for mc, burn, buyback in self._milestones[:5]
        ])

        announcement = (
            f"current marketcap: {self._format_number_with_dots(int(current_mc))}\n\n"
            f"{milestones_text}\n\n"            
        )
        
        # Update history and save
        self._announcement_history['initial_milestones'] = True
        self._save_announcement_history()
        
        return self._format_announcement_for_twitter(announcement)

    async def _monitor_marketcap(self):
        """Monitor marketcap and handle milestones"""
        try:
            last_update_time = 0  # Track last update time
            while True:
                current_mc = await self._check_marketcap()
                
                # Check if we've hit the next milestone
                if self._current_milestone_index < len(self._milestones):
                    next_milestone = self._milestones[self._current_milestone_index]
                    if current_mc >= next_milestone[0]:
                        await self._handle_milestone_reached(current_mc)
                
                # Only post marketcap update every 2 hours
                current_time = time.time()
                if current_time - last_update_time >= 3600:  # 7200 seconds = 2 hours
                    self._post_marketcap_update(current_mc)
                    last_update_time = current_time
                
                await asyncio.sleep(600)  # Check every 10 minutes (600 seconds)
        except Exception as e:
            logger.error(f"Error in marketcap monitoring: {e}")

    async def _handle_milestone_reached(self, current_mc: Decimal):
        """Handle reached milestone"""
        milestone = self._milestones[self._current_milestone_index]
        mc, burn_percentage, buyback_amount = milestone
        
        # Check if milestone was already executed
        mc_str = str(mc)  # Convert to string for consistent comparison
        if mc_str in [str(x) for x in self._announcement_history['milestone_executions']]:
            logger.info(f"Milestone {mc} was already executed, skipping...")
            self._current_milestone_index += 1
            return
        
        # Execute milestone
        announcement = None
        if mc == Decimal('1000000') or mc == Decimal('10000000'):
            announcement = await self._execute_special_milestone(burn_percentage, buyback_amount)
        else:
            announcement = await self._execute_standard_milestone(burn_percentage, buyback_amount)
        
        # Only update history if announcement was made successfully
        if announcement and "oopsie" not in announcement.lower():
            # Update history and save
            self._announcement_history['milestone_executions'].append(str(mc))
            self._save_announcement_history()
            logger.info(f"Added milestone {mc} to execution history")
        else:
            logger.error(f"Milestone {mc} execution failed or returned error message")
        
        self._current_milestone_index += 1

    def _post_marketcap_update(self, current_mc: Decimal):
        """Post regular marketcap update"""
        # Check if we recently posted about this marketcap
        mc_key = str(int(current_mc))
        last_update = self._announcement_history['marketcap_updates'].get(mc_key)
        
        if last_update and (time.time() - last_update < 21600):  # 6 hours in seconds
            return None

        # Get fresh narrative data from database with retries
        story_circle = None
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            story_circle = self.db.get_story_circle_sync()
            if story_circle and story_circle.get('events'):
                self.narrative = story_circle
                logger.info(f"Refreshed narrative data with {len(story_circle.get('events', []))} events")
                break
            else:
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: No story circle data yet, retrying...")
                time.sleep(retry_delay)  # Wait before retry
                retry_delay *= 4  # Exponential backoff
        
        # Skip announcement if no narrative context is available
        if not story_circle or not story_circle.get('events'):
            logger.warning("Skipping marketcap update - narrative context not available")
            return None

        # Store current marketcap in memories table
        try:
            marketcap_memory = f"Current marketcap: {current_mc}"
            self.memory_processor.store_marketcap_sync(marketcap_memory)
            logger.info(f"Successfully stored marketcap in memories: {marketcap_memory}")
        except Exception as e:
            logger.error(f"Failed to store marketcap in memories: {e}")

        # Get next unachieved milestone
        next_milestone = None
        for milestone, burn, buyback in self._milestones:
            if str(milestone) not in [str(x) for x in self._announcement_history['milestone_executions']]:
                next_milestone = milestone
                break
        
        # Only create announcement if there's an unachieved milestone
        if next_milestone:
            remaining = max(Decimal('0'), next_milestone - current_mc)
            
            # Create base announcement with formatted numbers
            base_announcement = (
                f"current marketcap: {self._format_number_with_dots(int(current_mc))}\n"
                f"next move target: {self._format_number_with_dots(int(next_milestone))}\n"
                f"we still need: {self._format_number_with_dots(int(remaining))} to make dis happen\n"
                "operation locked & loaded... we dont play"
            )

            try:
                # Extract narrative context
                dynamic_context = story_circle.get('dynamic_context', {})
                current_event = dynamic_context.get('current_event', '')
                inner_dialogue = dynamic_context.get('inner_dialogue', '') or dynamic_context.get('current_inner_dialogue', '')

                # Attempt AI generation with narrative context
                announcement = self.ai_announcements.generate_marketcap_announcement(
                    base_announcement,
                    current_event,
                    inner_dialogue
                )
                
                if announcement and announcement.strip():
                    logger.info("Successfully generated AI announcement")
                    logger.info("AI Generated Content:")
                    logger.info("-" * 50)
                    logger.info(f"Base Announcement:\n{base_announcement}")
                    logger.info(f"Current Event: {current_event}")
                    logger.info(f"Inner Dialogue: {inner_dialogue}")
                    logger.info(f"Generated Announcement:\n{announcement}")
                    logger.info("-" * 50)
                    logger.info(f"Broadcasting AI marketcap announcement to Telegram only: {announcement}")
                    asyncio.create_task(self.broadcaster.broadcast_telegram_only(announcement))
                else:
                    logger.warning("LLM returned empty announcement, falling back to base")
                    announcement = base_announcement
                    logger.info(f"Broadcasting base announcement to Telegram only: {announcement}")
                    asyncio.create_task(self.broadcaster.broadcast_telegram_only(announcement))
            except Exception as e:
                logger.error(f"Error in AI announcement generation: {str(e)}", exc_info=True)
                announcement = base_announcement
                logger.info(f"Broadcasting base announcement to Telegram only: {announcement}")
                asyncio.create_task(self.broadcaster.broadcast_telegram_only(announcement))
        else:
            # If all milestones are achieved, just post current marketcap to Telegram only
            announcement = f"current marketcap: {self._format_number_with_dots(int(current_mc))}"
            logger.info(f"Broadcasting milestone completion announcement to Telegram only: {announcement}")
            asyncio.create_task(self.broadcaster.broadcast_telegram_only(announcement))
        
        self._announcement_history['marketcap_updates'][mc_key] = time.time()
        self._save_announcement_history()
        
        return announcement

    def _load_announcement_history(self) -> dict:
        """Load announcement history from JSON file"""
        try:
            if self._announcements_file.exists():
                with open(self._announcements_file, 'r') as f:
                    history = json.load(f)
                    # Convert milestone executions to Decimal for consistency
                    history['milestone_executions'] = [
                        Decimal(str(x)) for x in history.get('milestone_executions', [])
                    ]
                    return history
            return {
                'wallet_announced': False,
                'tokens_received': False,
                'initial_milestones': False,
                'milestone_executions': [],
                'marketcap_updates': {}
            }
        except Exception as e:
            logger.error(f"Error loading announcement history: {e}")
            return {
                'wallet_announced': False,
                'tokens_received': False,
                'initial_milestones': False,
                'milestone_executions': [],
                'marketcap_updates': {}
            }

    def _save_announcement_history(self):
        """Save announcement history to JSON file with proper encoding"""
        try:
            # Convert all Decimal values to strings before saving
            history_copy = {
                'wallet_announced': self._announcement_history['wallet_announced'],
                'tokens_received': self._announcement_history['tokens_received'],
                'initial_milestones': self._announcement_history['initial_milestones'],
                'milestone_executions': [str(x) for x in self._announcement_history['milestone_executions']],
                'marketcap_updates': {
                    k: v for k, v in self._announcement_history['marketcap_updates'].items()
                }
            }
            
            with open(self._announcements_file, 'w') as f:
                json.dump(history_copy, f, indent=2)
            
            logger.info(f"Saved announcement history with {len(history_copy['milestone_executions'])} milestone executions")
        except Exception as e:
            logger.error(f"Error saving announcement history: {e}")

    def _format_number_with_dots(self, number: int) -> str:
        """Format large numbers with dots for better readability"""
        return f"{number:,}".replace(",", ".")