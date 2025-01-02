# prompts.py

import logging
import json
import os
from src.database.supabase_client import DatabaseService
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('prompts')

def load_style_prompts():
    """Load system prompt from YAML file"""
    try:
        yaml_path = os.path.join(os.path.dirname(__file__), 'prompts_config', 'system_prompt.yaml')
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
            # Extract system prompt from YAML
            if 'system_prompt' in config:
                return {
                    "style1": config['system_prompt'],
                    "style2": "not-used in conversation bots"  # Keep for backward compatibility
                }
            logger.error("No system_prompt found in YAML config")
            return None
    except Exception as e:
        logger.error(f"Error loading system prompt: {e}")
        return None

# Load prompts from JSON file
SYSTEM_PROMPTS = load_style_prompts() or {
    "style1": """Default prompt if JSON loading fails""",
    "style2": """not-used in conversation bots"""
}

TOPICS = [
    "not used in conversation bots"
]

class PromptManager:
    def __init__(self):
        self.db = DatabaseService()

    async def get_context(self):
        """Get current context from database"""
        try:
            story_circle = await self.db.get_story_circle()
            if not story_circle:
                return {}
            return story_circle['narrative']['dynamic_context']
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return {}

    async def get_memories(self):
        """Get memories from database"""
        try:
            return await self.db.get_memories()
        except Exception as e:
            logger.error(f"Error getting memories: {e}")
            return []
