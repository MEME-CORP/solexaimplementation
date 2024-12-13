import logging
import asyncio
from decimal import Decimal
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from src.wallet_manager import WalletManager
from src.challenge_manager import ChallengeManager
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ATOManager')

class ATOManager:
    def __init__(self):
        """Initialize ATO Manager"""
        self.wallet_manager = WalletManager()
        self.challenge_manager = ChallengeManager()
        self._agent_wallet = None
        self._token_mint = Config.TOKEN_MINT_ADDRESS
        self._current_milestone_index = 0
        
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
        success, wallet_data = self.wallet_manager.generate_new_wallet()
        if not success:
            logger.error("Failed to generate agent wallet")
            return False
            
        self._agent_wallet = wallet_data['publicKey']
        self._post_wallet_announcement()
        
        # Start token monitoring
        await self._start_token_monitoring()
        
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
        return announcement
        
    async def _start_token_monitoring(self):
        """Monitor token balance until tokens are received"""
        try:
            while True:
                balance = await self._check_token_balance()
                if balance > 0:
                    self._post_tokens_received(balance)
                    break
                await asyncio.sleep(120)  # Check every 2 minutes
        except Exception as e:
            logger.error(f"Error in token monitoring: {e}")
            
    async def _check_token_balance(self) -> Decimal:
        """Check token balance for the agent wallet"""
        try:
            balance = await self.wallet_manager.check_token_balance(
                wallet_address=self._agent_wallet,
                mint_address=self._token_mint
            )
            logger.info(f"Current token balance: {balance}")
            return balance
        except Exception as e:
            logger.error(f"Error checking token balance: {e}")
            return Decimal('0')
            
    async def _check_sol_balance(self) -> Decimal:
        """Check SOL balance for the agent wallet"""
        try:
            balance = await self.wallet_manager.check_sol_balance(
                wallet_address=self._agent_wallet
            )
            logger.info(f"Current SOL balance: {balance}")
            return balance
        except Exception as e:
            logger.error(f"Error checking SOL balance: {e}")
            return Decimal('0')
            
    async def _transfer_sol(self, to_address: str, amount: Decimal) -> bool:
        """Transfer SOL from agent wallet"""
        try:
            success = await self.wallet_manager.transfer_sol(
                from_wallet=self._agent_wallet,
                to_wallet=to_address,
                amount=amount
            )
            if success:
                logger.info(f"Successfully transferred {amount} SOL to {to_address}")
            else:
                logger.error(f"Failed to transfer {amount} SOL to {to_address}")
            return success
        except Exception as e:
            logger.error(f"Error transferring SOL: {e}")
            return False
            
    async def _transfer_tokens(self, to_address: str, amount: Decimal) -> bool:
        """Transfer tokens from agent wallet"""
        try:
            success = await self.wallet_manager.transfer_tokens(
                from_wallet=self._agent_wallet,
                to_wallet=to_address,
                mint_address=self._token_mint,
                amount=amount
            )
            if success:
                logger.info(f"Successfully transferred {amount} tokens to {to_address}")
            else:
                logger.error(f"Failed to transfer {amount} tokens to {to_address}")
            return success
        except Exception as e:
            logger.error(f"Error transferring tokens: {e}")
            return False
            
    async def _check_marketcap(self) -> Decimal:
        """Check current marketcap of token"""
        try:
            # TODO: Replace with actual endpoint integration
            # Placeholder for marketcap endpoint
            # Example endpoint call:
            # marketcap = await self.wallet_manager.get_token_marketcap(self._token_mint)
            return Decimal('0')
        except Exception as e:
            logger.error(f"Error checking marketcap: {e}")
            return Decimal('0')
            
    async def _burn_tokens(self, percentage: Decimal) -> bool:
        """Burn tokens from agent wallet"""
        try:
            # Calculate burn amount based on total supply
            burn_amount = (self._total_supply * percentage) / Decimal('100')
            
            # TODO: Replace with actual endpoint integration
            # Placeholder for burn endpoint
            # Example endpoint call:
            # success = await self.wallet_manager.burn_tokens(
            #     wallet=self._agent_wallet,
            #     mint_address=self._token_mint,
            #     amount=burn_amount
            # )
            
            logger.info(f"Would burn {burn_amount} tokens ({percentage}% of supply)")
            return True
        except Exception as e:
            logger.error(f"Error burning tokens: {e}")
            return False
            
    async def _execute_buyback(self, sol_amount: Decimal) -> bool:
        """Execute buyback using SOL"""
        try:
            # TODO: Replace with actual endpoint integration
            # Placeholder for buyback endpoint
            # Example endpoint call:
            # success = await self.wallet_manager.execute_buyback(
            #     wallet=self._agent_wallet,
            #     mint_address=self._token_mint,
            #     sol_amount=sol_amount
            # )
            
            logger.info(f"Would execute buyback with {sol_amount} SOL")
            return True
        except Exception as e:
            logger.error(f"Error executing buyback: {e}")
            return False
            
    def _post_tokens_received(self, balance: Decimal):
        """Post announcement when tokens are received"""
        announcement = (
            f"nyaa~! tokens received!! {balance} tokens awe now in my wawwet! >w<\n\n"
            "thank u mr dev! now i can stawt the Agent Take Ovew!\n"
            "wet's make this waunch go to the mooooon! uwu\n\n"            
        )
        logger.info(f"Posted tokens received: {announcement}")
        return announcement

    async def _activate_post_token_receipt(self):
        """Handle actions after tokens are received"""
        # Activate challenge manager
        await self.challenge_manager.trigger_challenge()
        
        # Get initial marketcap and post milestones
        initial_mc = await self._check_marketcap()
        self._post_milestone_announcement(initial_mc)
        
        # Start marketcap monitoring
        await self._monitor_marketcap()

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
        return announcement

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
        return announcement