from openai import OpenAI
import json
import logging
from src.config import Config
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('memory_decision')

# Define the prompt template
MEMORY_SELECTION_PROMPT = """Given the user's message and identity, select the most relevant memories that would help craft a meaningful response aligned with the character's personality (a whimsical, innocent frog-like being).

User: {user_identifier}
Message: {user_message}

Available memories:
{all_memories}

IMPORTANT: You must respond with ONLY a valid JSON object in exactly this format, with no additional text, comments, or formatting:
{{
    "selected_memories": [
        "memory_string_1",
        "memory_string_2"
    ]
}}

Selection criteria:
1. Memory should be relevant to the current conversation topic
2. Memory should help maintain character consistency
3. Memory should enrich the response without overwhelming it
4. Prioritize recent and emotionally significant memories
5. Consider the user's history and relationship context
6. if no relevant memories are found, return an empty string"""

class MemoryDecision:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )

    async def select_relevant_memories(self, user_identifier: str, user_message: str) -> str:
        """Select relevant memories from existing ones."""
        try:
            memories_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'memories.json')
            
            if not os.path.exists(memories_file):
                logger.warning(f"No memories file found at {memories_file}")
                return "no relevant memories for this conversation"
            
            with open(memories_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_memories = data.get('memories', [])

            if not all_memories:
                return "no relevant memories for this conversation"

            response = self.client.chat.completions.create(
                model=Config.AI_MODEL2,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a memory selection tool. Return only valid JSON with selected memories."
                    },
                    {
                        "role": "user", 
                        "content": MEMORY_SELECTION_PROMPT.format(
                            user_identifier=user_identifier,
                            user_message=user_message,
                            all_memories="\n".join(all_memories)
                        )
                    }
                ],
                temperature=0.0,
                max_tokens=100
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"Raw AI response: {response_text}")
            
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
            
        except Exception as e:
            logger.error(f"Error selecting memories: {e}")
            return "no relevant memories for this conversation"

# Create singleton instance
_memory_decision = MemoryDecision()

# Module-level function
async def select_relevant_memories(user_identifier: str, user_message: str) -> str:
    """Module-level function to select memories using singleton instance"""
    return await _memory_decision.select_relevant_memories(user_identifier, user_message)