from openai import OpenAI
import json
import logging
from src.config import Config

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
5. Consider the user's history and relationship context"""

class MemoryDecision:
    def __init__(self):
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )

    async def select_relevant_memories(self, user_identifier: str, user_message: str) -> str:
        """
        Select relevant memories based on the current conversation context.
        Returns a comma-separated string of relevant memories.
        """
        try:
            # Read all available memories
            with open('memories.json', 'r') as f:
                all_memories = json.load(f)['memories']
            
            # Get memory selection from AI
            response = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",  # Updated model name
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise memory selection tool. You MUST respond with ONLY a valid JSON object, with no additional text, comments, or formatting."
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
            
            # Parse response with extra safety checks
            response_text = response.choices[0].message.content.strip()
            
            # Debug logging
            logger.debug(f"Raw AI response: {response_text}")
            
            try:
                # Try to clean the response if it contains any markdown formatting
                if response_text.startswith('```json'):
                    response_text = response_text.replace('```json', '').replace('```', '').strip()
                elif response_text.startswith('```'):
                    response_text = response_text.replace('```', '').strip()
                
                # Parse the cleaned JSON
                selection = json.loads(response_text)
                
                # Validate the expected structure
                if not isinstance(selection, dict) or "selected_memories" not in selection:
                    logger.error("Invalid response structure")
                    return ""
                
                if not isinstance(selection["selected_memories"], list):
                    logger.error("selected_memories is not a list")
                    return ""
                
                return "\n".join(selection["selected_memories"])
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {e}\nRaw response: {response_text}")
                return ""
            
        except Exception as e:
            logger.error(f"Error selecting memories: {e}")
            return ""

# Create singleton instance
_memory_decision = MemoryDecision()

# Module-level function
async def select_relevant_memories(user_identifier: str, user_message: str) -> str:
    """Module-level function to select memories using singleton instance"""
    return await _memory_decision.select_relevant_memories(user_identifier, user_message)