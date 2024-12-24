from openai import OpenAI
import json
import logging
from src.config import Config
import os
from src.database.supabase_client import DatabaseService
from src.wallet_manager import WalletManager
import random
import yaml
import os.path
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('creativity_manager')

def load_yaml_prompt(filename):
    """Load a prompt from a YAML file"""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts_config', filename)
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_config = yaml.safe_load(f)
            return prompt_config.get('creativity_prompt', '')
    except Exception as e:
        logger.error(f"Error loading prompt from {filename}: {e}")
        return None

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

    async def _get_market_data(self):
        """Get current marketcap and next milestone"""
        try:
            # Get current marketcap from wallet manager
            success, balance_data = await self.wallet_manager.check_balance(
                Config.TOKEN_MINT_ADDRESS,
                Config.TOKEN_MINT_ADDRESS
            )
            
            if not success or not balance_data:
                logger.error("Failed to get balance data")
                return None, None
                
            current_marketcap = balance_data['token']['balance']
            next_milestone = self._milestones[0][0]  # Get first milestone
            
            return current_marketcap, next_milestone
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return None, None

    async def generate_creative_instructions(self, circles_memory):
        """Generate creative instructions for the next story circle update"""
        try:
            # Get current story circle state from database
            current_story_circle = self.db.get_story_circle()
            
            # Format the data to match expected structure
            formatted_story_circle = {
                "narrative": {
                    "current_story_circle": current_story_circle["phases"],
                    "current_phase": current_story_circle["current_phase"],
                    "events": current_story_circle["events"],
                    "inner_dialogues": current_story_circle["dialogues"],
                    "dynamic_context": current_story_circle["dynamic_context"]
                }
            }
            
            # Get real market data
            current_marketcap, next_milestone = await self._get_market_data()
            
            # Format the prompt with current data using the loaded YAML prompt
            formatted_prompt = self.creativity_prompt.format(
                current_story_circle=json.dumps(formatted_story_circle, indent=2, ensure_ascii=False),
                previous_summaries=json.dumps(circles_memory, indent=2, ensure_ascii=False),
                current_marketcap=current_marketcap,
                next_milestone=next_milestone
            )
            
            # Get the creativity instructions from the AI
            response = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=[
                    {"role": "system", "content": formatted_prompt},
                    {"role": "user", "content": "Generate creative instructions for the next story circle update, first in the <CS> tags and then in the exact YAML format specified in the <INSTRUCTIONS> tags. Ensure that marketcap numbers are mentioned explicitly in the first event and dialogue. "}
                ],
                temperature=0.0,
                max_tokens=4000
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extract instructions from the <INSTRUCTIONS> tags
            import re
            instructions_match = re.search(r'<INSTRUCTIONS>(.*?)</INSTRUCTIONS>', response_text, re.DOTALL)
            
            if instructions_match:
                instructions = instructions_match.group(1).strip()
                logger.info(f"Generated creative instructions successfully")
                return instructions
            else:
                logger.error("No instructions found in AI response")
                return "Create a compelling and unique story that develops Fwog's character in unexpected ways"
                
        except Exception as e:
            logger.error(f"Error generating creative instructions: {e}")
            return "Create a compelling and unique story that develops Fwog's character in unexpected ways"

    def get_emotion_format(self):
        """Get a random emotion format from database"""
        try:
            formats = self.db.get_emotion_formats()
            if not formats:
                return {"format": "default response", "description": "Standard emotional response"}
            return random.choice(formats)
        except Exception as e:
            logger.error(f"Error getting emotion format: {e}")
            return {"format": "default response", "description": "Standard emotional response"}

    def get_length_format(self):
        """Get a random length format from JSON file"""
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
        """Get a random topic from database"""
        try:
            topics = self.db.get_topics()
            if not topics:
                return {"topic": "pond life"}
            return random.choice(topics)
        except Exception as e:
            logger.error(f"Error getting topic: {e}")
            return {"topic": "pond life"} 