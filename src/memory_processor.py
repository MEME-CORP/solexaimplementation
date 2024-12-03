import json
from openai import OpenAI
import asyncio
from datetime import datetime
from src.config import Config
import logging
import os
from src.database.supabase_client import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('memory_processor')

# Initialize OpenAI client
client = OpenAI(
    api_key=Config.GLHF_API_KEY,
    base_url=Config.OPENAI_BASE_URL
)

MEMORY_ANALYSIS_PROMPT = """Analyze the following conversations and extract topics and summaries in JSON format. 
Compare these with existing memories to determine if they're new and relevant for the character (a whimsical, innocent frog-like being).

Existing memories for reference:
{existing_memories}

Today's conversations:
{conversations}

Provide analysis in the following JSON format only:
{{
    "topics": [
        {{
            "topic": "string",
            "summary": "string",
            "exists": boolean,
            "relevant": boolean,
            "reasoning": "string"
        }}
    ]
}}

Rules for relevancy:
1. Topic should be specific and granular details that are meaningful or interesting to remember.
2. Should be a personal experience or observation, like an anecdote or story that is meaningful to the character.
"""

class MemoryProcessor:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.db = DatabaseService()

    @staticmethod
    def format_conversations(user_conversations):
        """Format the day's conversations into a readable string"""
        formatted = []
        for user_id, messages in user_conversations.items():
            conversation = [
                f"{'Assistant' if msg['is_bot'] else 'User'}: {msg['content']}"
                for msg in messages
            ]
            formatted.extend(conversation)
        return "\n".join(formatted)

    async def update_memories(self, analyzed_topics):
        """Add only new and relevant memories to the database"""
        try:
            new_relevant_topics = [
                topic for topic in analyzed_topics 
                if not topic['exists'] and topic['relevant']
            ]
            if new_relevant_topics:
                await self.db.add_memories(new_relevant_topics)
                logger.info(f"Added {len(new_relevant_topics)} new relevant memories")
            else:
                logger.info("No new relevant memories to add")
        except Exception as e:
            logger.error(f"Error in update_memories: {e}")
            raise e

    async def analyze_daily_conversations(self, user_conversations):
        try:
            existing_memories = await self.db.get_memories()
            
            # Format conversations for analysis
            formatted_conversations = self.format_conversations(user_conversations)
            
            # Prepare prompt with existing memories
            prompt = MEMORY_ANALYSIS_PROMPT.format(
                existing_memories=json.dumps(existing_memories, indent=2),
                conversations=formatted_conversations
            )
            
            # Get analysis using new OpenAI client format
            response = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=[
                    {
                        "role": "system", 
                        "content": """You are a precise analysis tool that MUST respond with ONLY valid JSON format.
                        Do not include any explanatory text before or after the JSON.
                        The JSON must exactly match the requested format.
                        Do not include markdown formatting or code blocks."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=1000
            )
            
            # Log the raw response for debugging
            response_content = response.choices[0].message.content.strip()
            logger.info(f"Raw API Response: {response_content}")
            
            # Try to clean the response if needed
            cleaned_content = response_content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            cleaned_content = cleaned_content.strip()
            
            # Parse response with better error handling
            try:
                analysis = json.loads(cleaned_content)
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON Parse Error: {json_err}")
                logger.error(f"Attempted to parse: {cleaned_content}")
                # Provide a fallback analysis if parsing fails
                analysis = {
                    "topics": [
                        {
                            "topic": "conversation_parse_error",
                            "summary": "had twouble understanding the convewsation today... maybe twy again tomowwow?",
                            "exists": False,
                            "relevant": False,
                            "reasoning": "Error parsing conversation analysis"
                        }
                    ]
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in analyze_daily_conversations: {e}")
            raise e

    async def process_daily_memories(self, user_conversations):
        """Main function to process daily memories - should be called at night"""
        try:
            logger.info("Starting daily memory processing...")
            
            # First analyze the conversations
            analysis = await self.analyze_daily_conversations(user_conversations)
            
            # Then update the database with only new and relevant memories
            await self.update_memories(analysis['topics'])
            
            logger.info("Daily memory processing completed successfully")
            return analysis
        except Exception as e:
            logger.error(f"Error in process_daily_memories: {e}")
            raise e 