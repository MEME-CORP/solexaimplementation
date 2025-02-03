import json
import asyncio
from datetime import datetime
import logging
from src.config import Config
from src.creativity_manager import CreativityManager
from openai import OpenAI
import os
from src.database.supabase_client import DatabaseService
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('story_circle_manager')

# File paths
STORY_CIRCLE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'story_circle.json')
CIRCLES_MEMORY_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'circle_memories.json')

def load_yaml_prompt(filename):
    """Load a prompt from a YAML file"""
    try:
        # Get absolute path to the prompts_config directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(current_dir, 'prompts_config', filename)
        
        logger.info(f"Attempting to load prompt from: {prompt_path}")
        
        if not os.path.exists(prompt_path):
            logger.error(f"Prompt file not found: {prompt_path}")
            # Try alternative path resolution
            project_root = os.path.dirname(current_dir)
            alt_path = os.path.join(project_root, 'src', 'prompts_config', filename)
            
            if os.path.exists(alt_path):
                prompt_path = alt_path
                logger.info(f"Found prompt file at alternative path: {alt_path}")
            else:
                logger.error(f"Prompt file not found at alternative path: {alt_path}")
                return None
            
        with open(prompt_path, 'r', encoding='utf-8') as f:
            try:
                prompt_config = yaml.safe_load(f)
                logger.info(f"Loaded YAML content from {filename}: {type(prompt_config)}")
                
                if not prompt_config:
                    logger.error(f"Empty prompt configuration in {filename}")
                    return None
                
                # Check for either system_prompt or specific prompt keys
                prompt_text = None
                if 'system_prompt' in prompt_config:
                    prompt_text = prompt_config['system_prompt']
                    logger.info(f"Found system_prompt in {filename}")
                elif 'story_circle_prompt' in prompt_config and filename == 'story_circle_prompt.yaml':
                    prompt_text = prompt_config['story_circle_prompt']
                    logger.info(f"Found story_circle_prompt in {filename}")
                elif 'summary_prompt' in prompt_config and filename == 'summary_prompt.yaml':
                    prompt_text = prompt_config['summary_prompt']
                    logger.info(f"Found summary_prompt in {filename}")
                
                if not prompt_text:
                    logger.error(f"No valid prompt found in {filename}. Available keys: {list(prompt_config.keys())}")
                    return None
                
                logger.info(f"Successfully loaded prompt from {filename} (length: {len(str(prompt_text))})")
                return prompt_text
                
            except yaml.YAMLError as yaml_err:
                logger.error(f"YAML parsing error in {filename}: {str(yaml_err)}")
                return None
            
    except Exception as e:
        logger.error(f"Error loading prompt from {filename}: {str(e)}")
        logger.error(f"Current working directory: {os.getcwd()}")
        logger.error(f"File path attempted: {prompt_path}")
        return None

class StoryCircleManager:
    def __init__(self):
            self.client = OpenAI(
                api_key=Config.GLHF_API_KEY,
                base_url=Config.OPENAI_BASE_URL
            )

    def update_story_circle(self, creative_instructions=None):
        """Generate or update story circle based on creative instructions"""
        try:
            # Load story circle prompt template
            with open(os.path.join('src', 'prompts_config', 'story_circle_prompt.yaml')) as f:
                prompt_template = yaml.safe_load(f)['story_circle_prompt']
            
            # Instead of using format(), concatenate strings safely
            base_prompt = prompt_template.replace("{{circle_memories}}", "[]")  # Empty for testing
            if creative_instructions:
                # Add creative instructions at the end of the prompt
                full_prompt = f"{base_prompt}\n\nCreative Instructions:\n{creative_instructions}"
            else:
                full_prompt = base_prompt
            
            # Get new events from AI
            completion = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=[
                    {"role": "system", "content": full_prompt},
                    {
                        "role": "user", 
                        "content": (
                            "Generate a complete story circle, formatted as a JSON object. "
                            "The story circle should contain one to two highly detailed events and inner dialogues for each phase. "
                            "Focus on making each event rich in detail, compelling, and plausible. "
                            "Return ONLY valid JSON objects, exactly matching the template structure. "
                            "Do not include any additional text, markdown formatting, or explanations outside the JSON format."
                        )
                    }
                ],
                temperature=0.0,
                max_tokens=2000
            )
            
            response_text = completion.choices[0].message.content.strip()
            
            # Clean the response if it contains markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            return json.loads(response_text)
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            if 'response_text' in locals():
                logger.error(f"Raw response: {response_text}")
            raise

# Create a singleton instance
_manager = StoryCircleManager()

def update_story_circle():
    """Module-level function to update story circle using singleton instance - synchronous"""
    return _manager.update_story_circle()
