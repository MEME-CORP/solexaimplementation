# prompts.py

import logging
import json
import os
from src.database.supabase_client import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('prompts')

def load_style_prompts():
    """Load style prompts from JSON file"""
    try:
        json_path = os.path.join(os.path.dirname(__file__), 'prompts_config', 'style_prompt.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            prompts = json.load(f)
            
            # Format style1 prompt with ortho style
            if 'style1' in prompts:
                style1 = prompts['style1']
                ortho_style = json.dumps(style1['ortho_style'], indent=4)
                
                # Construct the full prompt with the same format as before
                prompts['style1'] = f"""{style1['description']}

ORTHO_BACK_STYLE
\"\"\"json
{ortho_style}
\"\"\"
END_ORTHO_BACK_STYLE
"""
            return prompts
    except Exception as e:
        logger.error(f"Error loading style prompts: {e}")
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
