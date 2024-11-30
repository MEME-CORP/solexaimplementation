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
    def __init__(self, mode='twitter'):
        self.mode = mode
        # Mode-specific settings
        if mode == 'twitter':
            self.max_tokens = 280
            self.temperature = 0.7
        elif mode == 'discord':
            self.max_tokens = 200  # Shorter responses for Discord
            self.temperature = 0.5  # Lower temperature for more consistent responses
        else:  # telegram or other
            self.max_tokens = 150
            self.temperature = 0.6
            
        self.system_prompt = SYSTEM_PROMPTS.get('style1', '')
        self.length_formats = self.load_length_formats()
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        
        self.model = Config.AI_MODEL2

    def load_length_formats(self):
        data_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'length_formats.json')
        with open(data_file, 'r', encoding='utf8') as f:
            data = json.load(f)
            return data.get('formats', [{"format": "default response"}])

    def clean_response(self, content):
        """Remove emojis and emoticons from response"""
        # Remove unicode emojis
        content = re.sub(r'[\U0001F300-\U0001F9FF]', '', content)
        # Remove :emoji: style
        content = re.sub(r':[a-zA-Z_]+:', '', content)
        # Remove ASCII emoticons
        content = re.sub(r'[\:;][\'"]?[-~]?[\)\(\]\[\{\}DPp]', '', content)
        return content.strip()

    def generate_content(self, user_message='', topic='', user_id=None, username=None, conversation_context='', memories=None, narrative_context=None):
        """Generate content synchronously"""
        try:
            random_format = random.choice(self.length_formats)['format']
            
            # Add stronger emoji restriction to system prompt
            discord_style = """
            Style Instructions for Discord:
            1. NEVER use emojis or emoticons of any kind
            2. Keep responses very short (1-2 sentences maximum)
            3. Use text-speak and casual language
            4. Replace 'r' with 'fw' and 'l' with 'w' in words
            5. Keep responses friendly but concise
            """
            
            # Determine the appropriate prompt based on mode and input
            if self.mode == 'twitter':
                if topic:
                    content_prompt = f"Generate a tweet about: {topic}"
                else:
                    content_prompt = f"Generate a friendly reply to this tweet: \"{user_message}\""
            else:
                content_prompt = user_message

            # Format memories and narrative context
            memory_context = ""
            if memories:
                if isinstance(memories, list):
                    memory_text = "\n- ".join(memories)
                    memory_context = f"\nRelevant memories:\n- {memory_text}"
                else:
                    memory_context = f"\nMemories:\n{memories}"

            narrative_info = ""
            if narrative_context:
                narrative_info = f"\nCurrent event: {narrative_context.get('current_event', '')}\nInner dialogue: {narrative_context.get('current_inner_dialogue', '')}"

            messages = [
                {
                    "role": "system",
                    "content": f"{self.system_prompt}\n{discord_style if self.mode == 'discord' else ''}"
                },
                {
                    "role": "user",
                    "content": f"""Previous conversation:
{conversation_context}

{memory_context}
{narrative_info}

New message from {username or user_id}: "{content_prompt}"

IMPORTANT RULES:
1. NEVER use emojis or emoticons
2. Keep your response very short
3. Let this emotion shape your response: {random_format}
4. Replace 'r' with 'fw' and 'l' with 'w'"""
                }
            ]

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

            content = response.choices[0].message.content
            
            # Clean the response
            cleaned_content = self.clean_response(content)
            
            return cleaned_content

        except Exception as e:
            logger.error(f"Error generating content: {e}")
            logger.error(f"Context: memories={memories}, narrative={narrative_context}")
            raise

