# creativity_manager.py

# Configure logging first
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('creativity_manager')

# Then rest of imports
import asyncio
import nest_asyncio
from openai import OpenAI
import json
import os
from src.config import Config
from src.database.supabase_client import DatabaseService
from src.wallet_manager import WalletManager
import random
import yaml
import os.path
from decimal import Decimal
from typing import Optional, Tuple

# Try importing pandas after logger is configured
try:
    import pandas as pd
except ImportError:
    logger.error("pandas package not found. Please install it using: pip install pandas")
    pd = None  # Set to None so we can check for it later

from datetime import datetime


def load_yaml_prompt(filename):
    """Load a prompt from a YAML file."""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts_config', filename)
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_config = yaml.safe_load(f)
            return prompt_config.get('creativity_prompt', '')
    except Exception as e:
        logger.error(f"Error loading prompt from {filename}: {e}")
        return None


def run_sync(coroutine):
    """
    Helper that runs an async coroutine in a synchronous manner.
    We apply 'nest_asyncio' so that if the main loop is already running,
    we can re-enter it without error.
    """
    try:
        loop = asyncio.get_event_loop()
        nest_asyncio.apply(loop)
        return loop.run_until_complete(coroutine)
    except RuntimeError:
        # If there's no running loop at all, create a new one
        new_loop = asyncio.new_event_loop()
        nest_asyncio.apply(new_loop)
        return new_loop.run_until_complete(coroutine)


class CreativityManager:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.db = DatabaseService()
        self.wallet_manager = WalletManager()
        
        # Load prompt from YAML file
        self.creativity_prompt = load_yaml_prompt('creativity_prompt.yaml')
        if not self.creativity_prompt:
            raise ValueError("Failed to load creativity prompt from YAML file")
        
        # Initialize milestones
        self._milestones = [
            (Decimal('75000'), Decimal('0.5'), Decimal('0.2')),
            (Decimal('150000'), Decimal('0.5'), Decimal('0.4')),
            (Decimal('300000'), Decimal('0.5'), Decimal('0.8')),
            (Decimal('600000'), Decimal('0.5'), Decimal('1.0')),
            (Decimal('1000000'), Decimal('0.5'), Decimal('1.5'))
        ]
        
        # Optional caching of the last known marketcap
        self._cached_marketcap: Optional[Decimal] = None
        self._cached_next_milestone: Optional[Decimal] = None
        
        # Add path for real-time events CSV
        self.events_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'real_time_events.csv')

    def _get_next_milestone(self, current_marketcap: Decimal) -> Decimal:
        """Get the next milestone based on current marketcap."""
        for milestone, _, _ in self._milestones:
            if milestone > current_marketcap:
                return milestone
        return self._milestones[-1][0]  # Return the highest milestone if we're past all others

    def _fetch_sync_marketcap(self) -> Tuple[bool, Optional[Decimal]]:
        """
        Actually await the wallet manager's async call so it behaves synchronously.
        """
        # The wallet_manager.get_token_marketcap is a coroutine, so we must run it in an event loop
        return run_sync(self.wallet_manager.get_token_marketcap(Config.TOKEN_MINT_ADDRESS))

    def _get_market_data(self) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Synchronously retrieve the marketcap from the async wallet manager.
        """
        try:
            # Instead of calling get_token_marketcap(...) directly, we do:
            success, marketcap = self._fetch_sync_marketcap()
            
            if not success or marketcap is None:
                logger.error("Failed to retrieve marketcap data (sync).")
                return None, None
            
            if not isinstance(marketcap, Decimal):
                logger.error("Marketcap is not a valid Decimal.")
                return None, None

            # Determine next milestone
            next_milestone = self._get_next_milestone(marketcap)

            # Cache the results
            self._cached_marketcap = marketcap
            self._cached_next_milestone = next_milestone
            logger.info(f"Synchronously retrieved marketcap: {marketcap}")
            
            return marketcap, next_milestone

        except Exception as e:
            logger.error(f"Error in _get_market_data: {e}")
            return None, None

    def update_cached_market_data(self, marketcap: Decimal) -> None:
        """
        If ATO Manager retrieves a fresh marketcap, call this to sync it here.
        """
        try:
            self._cached_marketcap = marketcap
            self._cached_next_milestone = self._get_next_milestone(marketcap)
            logger.info(f"Cached marketcap updated: {marketcap}")
        except Exception as e:
            logger.error(f"Error updating cached market data: {e}")

    def _get_real_time_events(self):
        """Get active real-time events from CSV file."""
        try:
            if pd is None:
                logger.error("pandas module not available")
                return "No real-time events available - pandas module missing"
            
            if not os.path.exists(self.events_path):
                logger.error(f"Real-time events file not found at: {self.events_path}")
                return "No real-time events available"
            
            df = pd.read_csv(self.events_path)
            active_events = df[df['status'] == 'active']
            
            if active_events.empty:
                return "No active real-time events"
            
            # Get the most recent events
            latest_events = active_events.iloc[-1]
            return latest_events['events']
            
        except Exception as e:
            logger.error(f"Error reading real-time events: {e}")
            return "Error retrieving real-time events"

    def generate_creative_instructions(self, circles_memory):
        """
        Synchronously generate creative instructions, including the marketcap data and real-time events.
        """
        try:
            # 1) Load current story circle from database
            current_story_circle = self.db.get_story_circle()
            if not current_story_circle:
                logger.warning("No story circle found in database.")
                return "Create a simple story because no circle was found."
            
            # 2) Prepare the current story circle data for the prompt
            formatted_story_circle = {
                "narrative": {
                    "current_story_circle": current_story_circle.get("phases", []),
                    "current_phase": current_story_circle.get("current_phase", ""),
                    "events": current_story_circle.get("events", []),
                    "inner_dialogues": current_story_circle.get("dialogues", []),
                    "dynamic_context": current_story_circle.get("dynamic_context", {})
                }
            }
            
            # 3) Retrieve marketcap synchronously
            current_marketcap, next_milestone = self._get_market_data()
            
            # If we still don't have marketcap info, produce fallback instructions
            if not current_marketcap or not next_milestone:
                logger.warning("Market data missing; using fallback instructions.")
                return "Create a compelling and unique story that develops the character's personality in unexpected ways"
            
            # Get real-time events
            real_time_events = self._get_real_time_events()
            
            # Format the creativity prompt with real-time events
            formatted_prompt = self.creativity_prompt.format(
                current_story_circle=json.dumps(formatted_story_circle, indent=2, ensure_ascii=False),
                previous_summaries=json.dumps(circles_memory, indent=2, ensure_ascii=False),
                current_marketcap=float(current_marketcap),
                next_milestone=float(next_milestone),
                real_time_events=real_time_events
            )
            
            # 5) Call the OpenAI Chat Completion endpoint
            response = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=[
                    {"role": "system", "content": formatted_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Generate creative instructions for the next story circles, "
                            "first in the <CS> tags and then in the exact YAML format specified in "
                            "the <INSTRUCTIONS> tags. "
                        )
                    }
                ],
                temperature=0.0,
                max_tokens=4000
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Add debug logging
            logger.info("=== DEBUG: LLM Response Start ===")
            logger.info(response_text)
            logger.info("=== DEBUG: LLM Response End ===")

            # 6) Extract instructions from the <INSTRUCTIONS> tags
            import re
            instructions_match = re.search(r'<INSTRUCTIONS>(.*?)</INSTRUCTIONS>', response_text, re.DOTALL)
            
            if instructions_match:
                instructions = instructions_match.group(1).strip()
                # Add debug logging for extracted instructions
                logger.info("=== DEBUG: Extracted Instructions Start ===")
                logger.info(instructions)
                logger.info("=== DEBUG: Extracted Instructions End ===")
                logger.info("Creative instructions successfully generated.")
                return instructions
            else:
                logger.error("No <INSTRUCTIONS> block found in AI response.")
                return "Create a compelling and unique story that develops the character's character in unexpected ways"
                
        except Exception as e:
            logger.error(f"Error in generate_creative_instructions: {e}")
            # Add debug logging for exception details
            logger.error("=== DEBUG: Exception Details ===")
            import traceback
            logger.error(traceback.format_exc())
            logger.error("=== DEBUG: Exception End ===")
            return "Create a compelling and unique story that develops the character's character in unexpected ways"

    def get_emotion_format(self):
        """Get a random emotion format from database."""
        try:
            formats = self.db.get_emotion_formats()
            if not formats:
                return {"format": "default response", "description": "Standard emotional response"}
            return random.choice(formats)
        except Exception as e:
            logger.error(f"Error getting emotion format: {e}")
            return {"format": "default response", "description": "Standard emotional response"}

    def get_length_format(self):
        """Get a random length format from JSON file."""
        try:
            file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'length_formats.json')
            with open(file_path, 'r') as f:
                data = json.load(f)
                formats = data.get('formats', [])
                if not formats:
                    return {"format": "one short sentence", "description": "Single concise sentence"}
                return random.choice(formats)
        except Exception as e:
            logger.error(f"Error getting length format: {e}")
            return {"format": "one short sentence", "description": "Single concise sentence"}

    def get_random_topic(self):
        """Get a random topic from database."""
        try:
            topics = self.db.get_topics()
            if not topics:
                return {"topic": "pond life"}
            return random.choice(topics)
        except Exception as e:
            logger.error(f"Error getting topic: {e}")
            return {"topic": "pond life"}
