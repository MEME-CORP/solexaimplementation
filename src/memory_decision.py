from openai import OpenAI
import json
import logging
from src.config import Config
import os
import yaml
from typing import Union, Tuple
from src.database.supabase_client import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('memory_decision')

def load_yaml_prompt(filename):
    """Load a prompt from a YAML file"""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts_config', filename)
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_config = yaml.safe_load(f)
            return prompt_config.get('memory_selection_prompt', '')
    except Exception as e:
        logger.error(f"Error loading prompt from {filename}: {e}")
        return None



class MemoryDecision:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.db = DatabaseService()
        
        # Load prompt from YAML file
        self.memory_selection_prompt = load_yaml_prompt('memory_selection_prompt.yaml')
        if not self.memory_selection_prompt:
            raise ValueError("Failed to load memory selection prompt from YAML file")

    def select_relevant_memories(self, user_identifier: str, user_message: str, return_details=False) -> Union[str, Tuple[str, dict]]:
        """Select relevant memories from existing ones."""
        try:
            all_memories = self.db.get_memories()
            
            if not all_memories:
                return ("no relevant memories for this conversation", {}) if return_details else "no relevant memories for this conversation"

            # Use instance prompt instead of global constant
            prompt = self.memory_selection_prompt.format(
                user_identifier=user_identifier,
                user_message=user_message,
                all_memories="\n".join(all_memories)
            )

            response = self.client.chat.completions.create(
                model=Config.AI_MODEL2,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a memory selection tool. Return only valid JSON with selected memories."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.0,
                max_tokens=100
            )
            
            response_text = response.choices[0].message.content.strip()
            
            memories = self._process_memory_response(response_text, all_memories)
            
            if return_details:
                details = {
                    'model': Config.AI_MODEL2,
                    'temperature': 0.0,
                    'max_tokens': 100,
                    'prompt': prompt,
                    'response': response_text
                }
                return memories, details
            
            return memories
            
        except Exception as e:
            logger.error(f"Error selecting memories: {e}")
            return ("no relevant memories for this conversation", {}) if return_details else "no relevant memories for this conversation"

    def _process_memory_response(self, response_text: str, all_memories: list) -> str:
        """Process the memory response and return the selected memories."""
        try:
            # Clean any markdown formatting
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            selection = json.loads(response_text)
            
            if not isinstance(selection, dict) or "selected_memories" not in selection:
                logger.error("Invalid response structure")
                return "no relevant memories for this conversation"
            
            valid_memories = [mem for mem in selection["selected_memories"] if mem in all_memories]
            
            if not valid_memories:
                return "no relevant memories for this conversation"
                
            return "\n".join(valid_memories)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}\nRaw response: {response_text}")
            return "no relevant memories for this conversation"

# Create singleton instance
_memory_decision = MemoryDecision()

# Module-level function
def select_relevant_memories(user_identifier: str, user_message: str, return_details=False) -> Union[str, Tuple[str, dict]]:
    """Module-level function to select memories using singleton instance"""
    return _memory_decision.select_relevant_memories(user_identifier, user_message, return_details)