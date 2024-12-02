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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ai_generator')

class AIGenerator:
    def __init__(self, mode='twitter'):
        self.mode = mode
        
        # Initialize these first
        logger.info("Initializing AIGenerator")
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
        data_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'length_formats.json')
        with open(data_file, 'r', encoding='utf8') as f:
            data = json.load(f)
            return data.get('formats', [{"format": "one short sentence", "description": "Single concise sentence"}])

    def load_emotion_formats(self):
        """Load emotion formats for response generation"""
        data_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'emotion_formats.json')
        with open(data_file, 'r', encoding='utf8') as f:
            data = json.load(f)
            return data.get('formats', [{"format": "default response", "description": "Standard emotional response"}])

    # Add these new methods after the existing load methods
    def load_memories(self):
        """Load memories from JSON file"""
        try:
            data_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'memories.json')
            logger.info(f"Attempting to load memories from: {os.path.abspath(data_file)}")
            
            if not os.path.exists(data_file):
                logger.error(f"Memories file not found at: {os.path.abspath(data_file)}")
                return []
            
            with open(data_file, 'r', encoding='utf8') as f:
                data = json.load(f)
                memories = data.get('memories', [])
                logger.info(f"Successfully loaded {len(memories)} memories")
                return memories
        except Exception as e:
            logger.error(f"Error loading memories: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return []

    def load_narrative(self):
        """Load narrative context from JSON file"""
        try:
            data_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'story_circle.json')
            logger.info(f"Attempting to load narrative from: {os.path.abspath(data_file)}")
            
            if not os.path.exists(data_file):
                logger.error(f"Narrative file not found at: {os.path.abspath(data_file)}")
                return {}
            
            with open(data_file, 'r', encoding='utf8') as f:
                data = json.load(f)
                narrative = data.get('narrative', {})
                logger.info(f"Successfully loaded narrative with keys: {list(narrative.keys())}")
                return narrative
        except Exception as e:
            logger.error(f"Error loading narrative: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return {}

    def _prepare_messages(self, **kwargs):
        """Prepare messages for API call - exposed for testing"""
        # Get memories and narrative from kwargs or fall back to class properties
        memories = kwargs.get('memories', self.memories)
        narrative_context = kwargs.get('narrative_context', self.narrative.get('dynamic_context', {}))
        
        # Process memories to ensure proper format
        if isinstance(memories, str):
            if memories.strip() == "" or memories == "no relevant memories for this conversation":
                memory_context = "no relevant memories for this conversation"
            else:
                memory_context = memories
        else:
            memory_context = "no relevant memories for this conversation"
        
        # Select appropriate formats based on mode
        if self.mode == 'twitter':
            emotion_format = random.choice(self.emotion_formats)['format']
            length_format = random.choice(self.length_formats)['format']
            
            # Extract tweet content with simpler handling
            if kwargs.get('topic'):
                tweet_content = kwargs.get('topic')
            else:
                user_message = kwargs.get('user_message', '')
                if user_message:
                    # Handle "reply to:" format
                    if user_message.startswith('reply to:'):
                        tweet_content = user_message[9:].strip()  # Remove "reply to: " prefix
                    else:
                        tweet_content = user_message
                    logger.debug(f"Processing tweet content: {tweet_content}")
                else:
                    # New simplified tweet content for posting
                    tweet_content = "your current event and inner dialogue"
                    logger.info("Using narrative-based tweet content")

            # Build Twitter-specific prompt with exact format
            content_prompt = (
                f"Talk about {tweet_content}. Format the response as: {length_format}; let this emotion shape your response: {emotion_format}. "
                f"Remember to respond like a text message (max. 280 characters) "
                f"using text-speak and replacing 'r' with 'fw' and 'l' with 'w', "
                f"adhering to the format and format-length. "
                f"And do not use emojis/visual-emojis nor quotes or any other characters, just plain text and ascii-emoticons if appropiate.\n\n"
                f"memories: {memory_context}\n"
                f"previous conversations: {kwargs.get('conversation_context', '')}\n"
                f"current event: {narrative_context.get('current_event', '') if narrative_context else ''}\n"
                f"inner dialogue: {narrative_context.get('current_inner_dialogue', '') if narrative_context else ''}"
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
                f"where the current event is: {narrative_context.get('current_event', '') if narrative_context else ''} "
                f"and the inner dialogue to such an event is: {narrative_context.get('current_inner_dialogue', '') if narrative_context else ''}.\n\n"
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
            logger.info(f"Current memories: {self.memories}")
            logger.info(f"Current narrative: {self.narrative}")
            
            # For random tweet posts, use current event for memory selection
            if self.mode == 'twitter' and kwargs.get('user_message') is None:
                narrative_context = kwargs.get('narrative_context', {})
                current_event = narrative_context.get('current_event', '')
                
                # Use current event for memory selection instead of user message
                memories = kwargs.get('memories', self.memories)
                if not memories or memories == "no relevant memories for this conversation":
                    logger.info("No specific memories for random tweet, using current event context")
                    memories = f"Current event context: {current_event}"
            else:
                memories = kwargs.get('memories', self.memories)
            
            messages = self._prepare_messages(
                memories=memories,
                **kwargs
            )
            
            logger.info(f"Generating response with mode: {self.mode}")
            logger.debug(f"System prompt: {messages[0]['content']}")
            logger.debug(f"User message: {messages[1]['content']}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                presence_penalty=0.6,
                frequency_penalty=0.6
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            logger.error(f"Context: memories={self.memories}, narrative={self.narrative}")
            raise

