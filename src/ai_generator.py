# src/ai_generator.py

from openai import OpenAI
import random
import json
from src.config import Config
from src.prompts import SYSTEM_PROMPTS
import logging
import os
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ai_generator')

class AIGenerator:
    # Discord style as a class attribute
    discord_style = """
    Style Instructions for Discord:
    1. NEVER use emojis or emoticons of any kind
    2. Keep responses very short (1-2 sentences maximum)
    3. Use text-speak and casual language
    4. Replace 'r' with 'fw' and 'l' with 'w' in words
    5. Keep responses friendly but concise
    """

    def __init__(self, mode='twitter'):
        self.mode = mode
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

    def _prepare_messages(self, **kwargs):
        """Prepare messages for API call - exposed for testing"""
        # Select appropriate formats based on mode
        if self.mode == 'twitter':
            emotion_format = random.choice(self.emotion_formats)['format']
            length_format = random.choice(self.length_formats)['format']
            memory_context = kwargs.get('memories') if kwargs.get('memories') else "no relevant memories for this conversation"
            
            # Extract tweet content for replies
            if not kwargs.get('topic'):
                # Extract content between quotes from "Generate a friendly reply to this tweet: "actual content""
                tweet_match = re.search(r'"([^"]*)"', kwargs.get('user_message'))
                tweet_content = tweet_match.group(1) if tweet_match else kwargs.get('user_message')
            else:
                tweet_content = kwargs.get('topic')

            # Build Twitter-specific prompt with exact format
            content_prompt = (
                f"Talk about {tweet_content}. Format the response as: {length_format}; let this emotion shape your response: {emotion_format}. "
                f"Remember to respond like a text message (max. 280 characters) "
                f"using text-speak and replacing 'r' with 'fw' and 'l' with 'w', "
                f"adhering to the format and format-length. "
                f"And do not use emojis nor quotes or any other characters, just plain text.\n\n"
                f"memories: {memory_context}\n"
                f"previous conversations: {kwargs.get('conversation_context', '')}\n"
                f"current event: {kwargs.get('narrative_context', {}).get('current_event', '') if kwargs.get('narrative_context') else ''}\n"
                f"inner dialogue: {kwargs.get('narrative_context', {}).get('current_inner_dialogue', '') if kwargs.get('narrative_context') else ''}"
            )
        else:
            # Discord and Telegram format
            emotion_format = random.choice(self.emotion_formats)['format']
            memory_context = kwargs.get('memories') if kwargs.get('memories') else "no relevant memories for this conversation"
            
            content_prompt = (
                f"Previous conversation:\n"
                f"{kwargs.get('conversation_context', '')}\n\n"
                f"New message from {kwargs.get('username') or kwargs.get('user_id')}: \"{kwargs.get('user_message')}\"\n\n"
                f"Let this emotion shape your response: {emotion_format}. "
                f"Remember to respond like a text message using text-speak and replacing 'r' with 'fw' and 'l' with 'w'. "
                f"And do not use emojis. Keep the conversation context in mind when responding; "
                f"keep your memories in mind when responding: {memory_context}. "
                f"Your character has an arc, if it seems relevant to your response, mention it, "
                f"where the current event is: {kwargs.get('narrative_context', {}).get('current_event', '') if kwargs.get('narrative_context') else ''} "
                f"and the inner dialogue to such an event is: {kwargs.get('narrative_context', {}).get('current_inner_dialogue', '') if kwargs.get('narrative_context') else ''}.\n\n"
                f"memories: {memory_context}"
            )

        messages = [
            {
                "role": "system",
                "content": f"{self.system_prompt}\n{self.discord_style if self.mode == 'discord' else ''}"
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
            messages = self._prepare_messages(**kwargs)
            
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
            logger.error(f"Error generating content: {e}")
            logger.error(f"Context: memories={kwargs.get('memories')}, narrative={kwargs.get('narrative_context')}")
            raise

