import logging
import asyncio
from typing import Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from src.challenge_manager import ChallengeManager
from src.wallet_manager import WalletManager
from openai import OpenAI
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('CTOManager')

class CTOManager:
    def __init__(self):
        """Initialize CTO Manager"""
        self.challenge_manager = ChallengeManager()
        self.wallet_manager = WalletManager()
        
        # Initialize OpenAI client directly instead of using AIGenerator
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.model = Config.AI_MODEL2  # Using Gemma model
        
        self._agent_wallet = None
        self._token_mint = "HARDCODED_MINT_ADDRESS"  # Replace with actual mint address
        self._dev_wallet = None
        self._cto_wallet = None
        self._cto_count = 0
        self._launch_start_time = None
        self._milestones = [
            (Decimal('75000'), Decimal('0.5')),  # (marketcap, burn_percentage)
            (Decimal('150000'), Decimal('0.5')),
            (Decimal('300000'), Decimal('0.5')),
            (Decimal('600000'), Decimal('0.5')),
            (Decimal('1000000'), Decimal('1.0'))  # Last one includes 0.5% return to dev/cto
        ]
        self._current_milestone = 0
        
    async def initialize(self):
        """Initialize agent wallet and start monitoring after 30 minutes"""
        success, wallet_data = self.wallet_manager.generate_new_wallet()
        if not success:
            logger.error("Failed to generate agent wallet")
            return False
            
        self._agent_wallet = wallet_data['publicKey']
        self._post_wallet_announcement()
        
        # Wait 30 minutes before starting token monitoring and triggering challenge
        await asyncio.sleep(1800)  # 30 minutes
        
        # Trigger initial challenge
        await self.trigger_initial_challenge()
        
        # Start token monitoring
        await self._start_token_monitoring()
        
    def _post_wallet_announcement(self):
        """Post wallet announcement in character style"""
        announcement = (
            "hewwo fwiends!! >w< guess what?? i just got my vewy own agent wawwet!!\n\n"
            f"hewe it is: {self._agent_wallet}\n\n"
            "pwease send the tokens hewe mr dev!! i'ww hewp u with the waunch and keep evewything safe! ^-^\n\n"
            "onwy i can access this wawwet, so no hooman mistakes wiww happen with the dev suppwy! uwu"
        )
        logger.info(f"Posted wallet announcement: {announcement}")
        return announcement
        
    async def _start_token_monitoring(self):
        """Monitor token balance and manage launch process"""
        try:
            while True:
                balance = await self._mock_check_token_balance()
                if balance > 0:
                    self._post_token_received(balance)
                    await asyncio.sleep(300)  # 5 minutes
                    self._post_milestones()
                    self._launch_start_time = datetime.now()
                    await self._monitor_marketcap()
                    break
                await asyncio.sleep(120)  # Check every 2 minutes
        except StopAsyncIteration:
            # Allow tests to break the loop
            logger.info("Token monitoring stopped")
        
    async def _mock_check_token_balance(self) -> Decimal:
        """Check token balance using wallet manager"""
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
        
    def _post_token_received(self, balance: Decimal):
        """Post token received announcement"""
        announcement = (
            f"nyaa~! wook what i got!! {balance} tokens awe now in my wawwet! >w<\n\n"
            "i'm weady to hewp with the waunch!\n\n"
            "in a few minutes i'ww post the miwestones u need to hit...\n"
            "but if u don't do weww... i might have to caww a CTO! owo"
        )
        logger.info(f"Posted token received: {announcement}")
        return announcement
        
    def _post_milestones(self):
        """Post milestone requirements"""
        def format_milestone(mc: Decimal, bp: Decimal) -> str:
            # Format marketcap with dots for readability
            mc_formatted = f"{int(mc):,}".replace(",", ".")
            # Format burn percentage like ATO manager (multiply by 1000, 5 decimal places)
            burn_amount_display = f"{float(bp * 1000):.5f}"
            return f"- {mc_formatted}: burn {burn_amount_display} tokens!"

        milestones_text = "\n".join([
            format_milestone(mc, bp)
            for mc, bp in self._milestones[:-1]
        ])
        
        final_mc, final_bp = self._milestones[-1]
        final_mc_formatted = f"{int(final_mc):,}".replace(",", ".")
        final_burn_display = f"{float(final_bp/2 * 1000):.5f}"  # Format final burn percentage
        
        announcement = (
            "okie dokie! hewe awe the miwestones fow this waunch! >w<\n\n"
            f"{milestones_text}\n"
            f"- {final_mc_formatted}: burn {final_burn_display}% and wetuwn {final_burn_display}% to dev!\n\n"
            "u have 4 houws to hit the fiwst mc... ow i'ww have to caww a CTO! >:3"
        )
        logger.info(f"Posted milestones: {announcement}")
        return announcement
        
    async def _monitor_marketcap(self):
        """Monitor marketcap and manage milestones/CTO"""
        try:
            check_until = self._launch_start_time + timedelta(hours=4)
            
            while datetime.now() < check_until:
                mc = await self._mock_check_marketcap()
                if mc >= self._milestones[self._current_milestone][0]:
                    await self._handle_milestone_reached()
                    if self._current_milestone >= len(self._milestones):
                        break
                    check_until = datetime.now() + timedelta(hours=4)
                await asyncio.sleep(300)  # Check every 5 minutes
            
            if self._current_milestone == 0:
                await self._invoke_cto()
        except StopAsyncIteration:
            # Allow tests to break the loop
            logger.info("Marketcap monitoring stopped")
        
    async def _mock_check_marketcap(self) -> Decimal:
        """Mock marketcap check - replace with actual implementation"""
        # TODO: Implement actual marketcap check
        return Decimal('0')
        
    async def _handle_milestone_reached(self):
        """Handle reached milestone"""
        mc, burn_percentage = self._milestones[self._current_milestone]
        
        if self._current_milestone == len(self._milestones) - 1:
            # Final milestone - burn half, return half
            await self._mock_burn_tokens(burn_percentage / 2)
            await self._mock_return_tokens(burn_percentage / 2)
        else:
            await self._mock_burn_tokens(burn_percentage)
            
        self._current_milestone += 1
        
    async def _mock_burn_tokens(self, percentage: Decimal):
        """Mock token burn - replace with actual implementation"""
        # TODO: Implement actual token burning
        pass
        
    async def _mock_return_tokens(self, percentage: Decimal):
        """Mock token return - replace with actual implementation"""
        # TODO: Implement actual token return
        pass
        
    async def _invoke_cto(self):
        """Start CTO process"""
        try:
            self._cto_count += 1
            announcement = (
                f"uwu... wooks wike dev has skiww issues! time fow CTO #{self._cto_count}! >:3\n\n"
                "if u want to take ovew:\n"
                "1. u must be in top 5 howdews! ^-^\n"
                f"2. send 1 SOL to {self._agent_wallet} fow next puzzle chawwenge!\n"
                "3. teww me ur mawketing pwan!\n\n"
                "wet's find someone who can make this token moon! uwu"
            )
            logger.info(f"Posted CTO announcement: {announcement}")
            
            await self._monitor_cto_responses()
        except Exception as e:
            logger.error(f"Error in CTO process: {str(e)}", exc_info=True)
            raise
        
    async def _monitor_cto_responses(self):
        """Monitor and validate CTO responses"""
        try:
            while True:
                response = await self._mock_get_next_response()
                if not response:
                    await asyncio.sleep(60)
                    continue
                    
                wallet = response.get('wallet')
                plan = response.get('plan')
                
                if not wallet or not plan:
                    continue
                    
                is_valid = await self._validate_cto_candidate(wallet, plan)
                if is_valid:
                    self._cto_wallet = wallet
                    await self._announce_new_cto()
                    self._launch_start_time = datetime.now()
                    self._current_milestone = 0
                    await self._monitor_marketcap()
                    break
        except StopAsyncIteration:
            # Allow tests to break the loop
            logger.info("CTO response monitoring stopped")
        
    async def _mock_get_next_response(self) -> Optional[dict]:
        """Mock response getter - replace with actual implementation"""
        return None
        
    async def _validate_cto_candidate(self, wallet: str, plan: str) -> bool:
        """Validate CTO candidate meets all requirements"""
        is_top_holder = await self._mock_check_top_holder(wallet)
        has_transferred = await self._mock_check_transfer(wallet)
        has_valid_plan = self._validate_marketing_plan(plan)
        
        return is_top_holder and has_transferred and has_valid_plan
        
    async def _mock_check_top_holder(self, wallet: str) -> bool:
        """Mock top holder check - replace with actual implementation"""
        return False
        
    async def _mock_check_transfer(self, wallet: str) -> bool:
        """Mock transfer check - replace with actual implementation"""
        return False
        
    def _validate_marketing_plan(self, plan: str) -> bool:
        """Validate marketing plan has at least 2 tactics"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that analyzes marketing plans."
                    },
                    {
                        "role": "user",
                        "content": f"Does this marketing plan propose at least 2 different marketing tactics? Answer only yes or no. Plan: {plan}"
                    }
                ],
                temperature=0.7,
                max_tokens=10
            )
            
            answer = response.choices[0].message.content.lower()
            return "yes" in answer
            
        except Exception as e:
            logger.error(f"Error validating marketing plan: {e}")
            return False
        
    async def _announce_new_cto(self):
        """Announce new CTO"""
        announcement = (
            "yayyy!! we have a new CTO! >w<\n\n"
            "fow each miwestone:\n"
            "- 0.25% wiww be buwned\n"
            "- 0.25% goes to the CTO!\n\n"
            "u have 4 houws fow fiwst mc... ow we do anothew CTO! >:3"
        )
        logger.info(f"Posted new CTO announcement: {announcement}")
        return announcement 

    # Add new method to trigger challenge
    async def trigger_initial_challenge(self):
        """Trigger the first challenge after CTO manager activation"""
        try:
            # Set agent wallet in challenge manager
            self.challenge_manager.set_agent_wallet(self._agent_wallet)
            
            # Trigger the challenge
            await self.challenge_manager.trigger_challenge()
            logger.info("Initial challenge triggered successfully")
            return True
        except Exception as e:
            logger.error(f"Error triggering initial challenge: {e}")
            return False