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
        self.memories = self.load_memories()
        self.narrative = self.load_narrative()
        
        logger.info(f"Initialization complete. Memories loaded: {bool(self.memories)}, Narrative loaded: {bool(self.narrative)}")

    def load_length_formats(self):
        """Load Twitter-specific length formats"""
        try:
            formats = self.db.get_length_formats()
            return formats if formats else [{"format": "one short sentence", "description": "Single concise sentence"}]
        except Exception as e:
            logger.error(f"Error loading length formats: {e}")
            return [{"format": "one short sentence", "description": "Single concise sentence"}]

    def load_emotion_formats(self):
        """Load emotion formats for response generation"""
        try:
            formats = self.db.get_emotion_formats()
            return formats if formats else [{"format": "default response", "description": "Standard emotional response"}]
        except Exception as e:
            logger.error(f"Error loading emotion formats: {e}")
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
        """Load narrative context from database"""
        try:
            narrative = self.db.get_story_circle()
            if narrative and 'narrative' in narrative:
                logger.info(f"Successfully loaded narrative with keys: {list(narrative['narrative'].keys())}")
                return narrative['narrative']
            return {}
        except Exception as e:
            logger.error(f"Error loading narrative: {str(e)}")
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
        
        # Simplify tweet content handling - remove topic logic
        user_message = kwargs.get('user_message') or ''  # Convert None to empty string
        tweet_content = (
            user_message[9:].strip() if user_message.startswith('reply to:') 
            else "your current event and inner dialogue"
        )
        
        # Select appropriate formats based on mode
        if self.mode == 'twitter':
            emotion_format = random.choice(self.emotion_formats)['format']
            length_format = random.choice(self.length_formats)['format']
            
            # Build Twitter-specific prompt with exact format
            content_prompt = (
                f"Talk about {tweet_content}. Format the response as: {length_format}; let this emotion shape your response: {emotion_format}. "
                f"Remember to respond like a text message (max. 280 characters) "
                f"using text-speak and replacing 'r' with 'fw' and 'l' with 'w', "
                f"adhering to the format and format-length. "
                f"And do not use emojis/visual-emojis nor quotes or any other characters, just plain text and ascii-emoticons if appropiate.\n\n"
                f"memories: {memory_context}\n"
                f"previous conversations: {kwargs.get('conversation_context', '')}\n"
                f"current event: {current_event}\n"
                f"inner dialogue: {inner_dialogue}"
            )
        else:
            # Discord and Telegram format
            emotion_format = random.choice(self.emotion_formats)['format']
            
            content_prompt = (
                f"Previous conversation:\n"
                f"{kwargs.get('conversation_context', '')}\n\n"
                f"New message from {kwargs.get('username') or kwargs.get('user_id')}: \"{kwargs.get('user_message', '')}\"\n\n"
                f"Let this emotion shape your response: {emotion_format}. "
                f"Remember to respond like a text message using text-speak and replacing 'r' with 'fw' and 'l' with 'w'. "
                f"And do not use emojis. Keep the conversation context in mind when responding; "
                f"keep your memories in mind when responding: {memory_context}. "
                f"Your character has an arc, if it seems relevant to your response, mention it, "
                f"where the current event is: {current_event} "
                f"and the inner dialogue to such an event is: {inner_dialogue}.\n\n"
                f"NOTE //do not use emojis/visual-emojis nor quotes or any other characters, just plain text and ascii-emoticons if appropiate."
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
                model=self.model,
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

