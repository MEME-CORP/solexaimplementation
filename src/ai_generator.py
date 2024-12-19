# src/ai_generator.py

from openai import OpenAI
import random
import json
from src.config import Config
from src.prompts import SYSTEM_PROMPTS
import logging
import os
import re
import os.path
import traceback
from src.database.supabase_client import DatabaseService
import yaml
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ai_generator')

class AIGenerator:
    def __init__(self, mode='twitter'):
        self.mode = mode
        
        # Initialize these first
        logger.info("Initializing AIGenerator")
        self.db = DatabaseService()
        self.memories = None
        self.narrative = None
        
        # Mode-specific settings
        if mode == 'twitter':
            self.max_tokens = 70
            self.temperature = 0.7
            self.length_formats = self.load_length_formats()
            self.emotion_formats = self.load_emotion_formats()
        elif mode == 'discord':
            self.max_tokens = 40
            self.temperature = 0.7
            self.emotion_formats = self.load_emotion_formats()
        else:  # telegram or other
            self.max_tokens = 40
            self.temperature = 0.7
            self.emotion_formats = self.load_emotion_formats()
            
        self.system_prompt = SYSTEM_PROMPTS.get('style1', '')
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        
        # Always use Gemma for direct user interactions
        self.model = Config.AI_MODEL2  # This is gemma-2-9b-it

        # Load memories and narrative after everything else is initialized
        logger.info("Loading memories and narrative")
        try:
            memories_response = self.db.get_memories()
            self.memories = memories_response if memories_response else []
            logger.info(f"Successfully loaded {len(self.memories)} memories")
        except Exception as e:
            logger.error(f"Error loading memories: {e}")
            self.memories = []

        try:
            self.narrative = self.db.get_story_circle_sync()
            if self.narrative:
                logger.info("Successfully loaded narrative")
            else:
                logger.warning("No narrative loaded")
        except Exception as e:
            logger.error(f"Error loading narrative: {e}")
            self.narrative = None

        # Load bot prompts
        self.bot_prompts = self._load_bot_prompts()
        
        logger.info(f"Initialization complete. Memories loaded: {bool(self.memories)}, Narrative loaded: {bool(self.narrative)}")

    def load_length_formats(self):
        """Load length formats from JSON file"""
        try:
            # Get the path to the length_formats.json file
            file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'length_formats.json')
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                formats = data.get('formats', [])
                if not formats:
                    logger.warning("No length formats found in file")
                    return [{"format": "one short sentence", "description": "Single concise sentence"}]
                return formats
                
        except Exception as e:
            logger.error(f"Error loading length formats from file: {e}")
            return [{"format": "one short sentence", "description": "Single concise sentence"}]

    def load_emotion_formats(self):
        """Load emotion formats from JSON file"""
        try:
            # Get the path to the emotion_formats.json file
            file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'emotion_formats.json')
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                formats = data.get('formats', [])
                if not formats:
                    logger.warning("No emotion formats found in file")
                    return [{"format": "default response", "description": "Standard emotional response"}]
                return formats
                
        except Exception as e:
            logger.error(f"Error loading emotion formats from file: {e}")
            return [{"format": "default response", "description": "Standard emotional response"}]

    def load_memories(self):
        """Load memories from database"""
        try:
            memories = self.db.get_memories()
            logger.info(f"Successfully loaded {len(memories)} memories")
            return memories
        except Exception as e:
            logger.error(f"Error loading memories: {str(e)}")
            return []

    def load_narrative(self):
        """Load narrative context"""
        try:
            story_circle = self.db.get_story_circle_sync()
            if story_circle:
                logger.info("Narrative content:")
                logger.info(f"Current Phase: {story_circle['narrative']['current_phase']}")
                logger.info(f"Current Event: {story_circle['narrative']['dynamic_context']['current_event']}")
                logger.info(f"Current Inner Dialogue: {story_circle['narrative']['dynamic_context']['current_inner_dialogue']}")
                return story_circle['narrative']
            else:
                logger.warning("No story circle found in database")
                return None
        except Exception as e:
            logger.error(f"Error loading narrative: {e}")
            return None

    def _load_bot_prompts(self):
        """Load bot prompts from YAML file"""
        try:
            prompts_path = Path(__file__).parent / 'prompts_config' / 'bot_prompts.yaml'
            with open(prompts_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading bot prompts: {e}")
            return {}

    def _prepare_messages(self, **kwargs):
        """Prepare messages for API call - exposed for testing"""
        # Simplify memory handling with more familiar pattern
        memories = kwargs.get('memories', self.memories)
        memory_context = (
            "no relevant memories for this conversation" 
            if not memories or (isinstance(memories, str) and memories.strip() in ["", "no relevant memories for this conversation"])
            else memories if isinstance(memories, str)
            else "no relevant memories for this conversation"
        )
        
        # Simplify narrative context extraction
        narrative_context = kwargs.get('narrative_context', self.narrative.get('dynamic_context', {}))
        current_event = narrative_context.get('current_event', '') if narrative_context else ''
        inner_dialogue = narrative_context.get('current_inner_dialogue', '') if narrative_context else ''
        
        # Get the appropriate prompt template based on mode
        if self.mode == 'twitter':
            prompt_template = self.bot_prompts.get('twitter', {}).get('content_prompt', '')
            tweet_content = (
                kwargs.get('user_message', '')[9:].strip() if kwargs.get('user_message', '').startswith('reply to:')
                else "your current event and inner dialogue"
            )
            emotion_format = random.choice(self.emotion_formats)['format']
            length_format = random.choice(self.length_formats)['format']
            
            content_prompt = prompt_template.format(
                tweet_content=tweet_content,
                length_format=length_format,
                emotion_format=emotion_format,
                memory_context=memory_context,
                conversation_context=kwargs.get('conversation_context', ''),
                current_event=current_event,
                inner_dialogue=inner_dialogue
            )
        else:
            # Discord and Telegram format
            prompt_template = self.bot_prompts.get('discord_telegram', {}).get('content_prompt', '')
            emotion_format = random.choice(self.emotion_formats)['format']
            
            content_prompt = prompt_template.format(
                conversation_context=kwargs.get('conversation_context', ''),
                username=kwargs.get('username') or kwargs.get('user_id'),
                user_message=kwargs.get('user_message', ''),
                emotion_format=emotion_format,
                memory_context=memory_context,
                current_event=current_event,
                inner_dialogue=inner_dialogue
            )

        messages = [
            {
                "role": "system",
                "content": f"{self.system_prompt}"
            },
            {
                "role": "user",
                "content": content_prompt
            }
        ]

        return messages

    def generate_content(self, **kwargs):
        """Generate content synchronously"""
        try:
            logger.info("Starting content generation")
            
            # Simplified memory handling for random tweets
            memories = kwargs.pop('memories', self.memories)
            if self.mode == 'twitter' and not kwargs.get('user_message'):
                narrative_context = kwargs.get('narrative_context', {})
                current_event = narrative_context.get('current_event', '')
                if not memories or memories == "no relevant memories for this conversation":
                    logger.info("Using current event context for random tweet")
                    memories = f"Current event context: {current_event}"
            
            messages = self._prepare_messages(memories=memories, **kwargs)
            
            logger.debug(f"Generating with config: mode={self.mode}, model={self.model}, temp={self.temperature}")
            
            response = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",  # Update model name
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                presence_penalty=0.6,
                frequency_penalty=0.6
            )
            
            generated_content = response.choices[0].message.content
            
            # Validate response
            if not generated_content or not isinstance(generated_content, str):
                logger.error("Invalid response generated")
                raise ValueError("Generated content is invalid")
            
            if self.mode == 'twitter' and len(generated_content) > 280:
                logger.warning("Generated content exceeds Twitter limit, truncating")
                generated_content = generated_content[:277] + "..."
            
            return generated_content

        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            logger.error(f"Context: memories={self.memories}, narrative={self.narrative}")
            raise

