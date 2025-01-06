import json
from openai import OpenAI
import asyncio
from datetime import datetime
from src.config import Config
import logging
import os
import yaml
from src.database.supabase_client import DatabaseService
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('memory_processor')

def load_yaml_prompt(filename):
    """Load a prompt from a YAML file"""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts_config', filename)
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_config = yaml.safe_load(f)
            return prompt_config.get('memory_analysis_prompt', '')
    except Exception as e:
        logger.error(f"Error loading prompt from {filename}: {e}")
        return None

# Initialize OpenAI client
client = OpenAI(
    api_key=Config.GLHF_API_KEY,
    base_url=Config.OPENAI_BASE_URL
)



class MemoryProcessor:
    def __init__(self):
        """Initialize the memory processor"""
        self.memories = []
        self.processing_queue = asyncio.Queue()
        self.db = DatabaseService()
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        
        # Load prompt from YAML file
        self.memory_analysis_prompt = load_yaml_prompt('memory_analysis_prompt.yaml')
        if not self.memory_analysis_prompt:
            logger.warning("Failed to load memory analysis prompt from YAML file")

    async def store_announcement(self, announcement: str) -> bool:
        """Asynchronously store and process an announcement"""
        try:
            # Format the memory
            memory = {
                'timestamp': datetime.now().isoformat(),
                'content': announcement,
                'processed': False
            }
            
            # Store in database
            success = self.db.insert_memory(announcement)
            if not success:
                logger.error("Failed to store memory in database")
                return False
                
            # Add to local memories list
            self.memories.append(memory)
            
            # Add to processing queue
            await self.processing_queue.put(memory)
            
            logger.info(f"Successfully stored memory in database: {announcement[:100]}...")
            return True
            
        except Exception as e:
            logger.error(f"Error storing announcement: {e}")
            return False

    def store_announcement_sync(self, announcement: str) -> bool:
        """Synchronously store an announcement"""
        try:
            # Format the memory data properly
            memory_data = {
                'memory': announcement,  # Changed from 'content' to 'memory' to match schema
                'created_at': datetime.now().isoformat()
            }
            
            # Store in database using the correct format
            success = self.db.insert_memory(memory_data)
            if not success:
                logger.error("Failed to store memory in database")
                return False
                
            # Add to local memories list
            self.memories.append(memory_data)
            
            logger.info(f"Successfully stored announcement in database: {announcement[:100]}...")
            return True
            
        except Exception as e:
            logger.error(f"Error storing announcement synchronously: {e}")
            return False

    async def process_memories(self):
        """Process memories from the queue"""
        while True:
            try:
                # Get memory from queue
                memory = await self.processing_queue.get()
                
                # Process the memory
                await self._process_memory(memory)
                
                # Mark task as done
                self.processing_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing memory: {e}")
                continue

    async def _process_memory(self, memory: dict):
        """Process a single memory"""
        try:
            # Add processing logic here
            memory['processed'] = True
            logger.info(f"Processed memory: {memory['content'][:100]}...")
            
        except Exception as e:
            logger.error(f"Error in memory processing: {e}")
            raise

    def get_memories(self) -> List[dict]:
        """Get all stored memories from database"""
        try:
            memories = self.db.get_memories()
            return memories if memories else []
        except Exception as e:
            logger.error(f"Error getting memories: {e}")
            return []

    def clear_memories(self):
        """Clear all stored memories"""
        try:
            success = self.db.clear_memories()
            if success:
                self.memories = []
                logger.info("Successfully cleared all memories")
            else:
                logger.error("Failed to clear memories from database")
        except Exception as e:
            logger.error(f"Error clearing memories: {e}")

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

    async def analyze_daily_conversations(self, user_conversations):
        """Analyze conversations using AI"""
        try:
            # Get existing memories and ensure they're properly formatted
            raw_memories = self.get_memories()
            formatted_existing = []
            
            # Handle both string and dict memory formats
            for memory in raw_memories:
                if isinstance(memory, str):
                    formatted_existing.append(memory)
                elif isinstance(memory, dict):
                    formatted_existing.append(memory.get('content', ''))
                    
            # Format today's conversations
            formatted_conversations = self.format_conversations(user_conversations)
            
            if not self.memory_analysis_prompt:
                logger.error("Memory analysis prompt not loaded")
                return {"topics": []}

            # Format the prompt with properly formatted memories and conversations
            prompt = self.memory_analysis_prompt.format(
                existing_memories="\n".join(formatted_existing),
                conversations=formatted_conversations
            )
            
            logger.info(f"Sending prompt to LLM with {len(formatted_existing)} existing memories")
            
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
            
            response_content = response.choices[0].message.content.strip()
            logger.info(f"LLM Analysis Response: {response_content[:200]}...")
            
            try:
                analysis = json.loads(response_content)
                return analysis
            except json.JSONDecodeError as e:
                logger.error(f"JSON Parse Error: {e}")
                return {"topics": []}
                
        except Exception as e:
            logger.error(f"Error in analyze_daily_conversations: {e}")
            logger.exception("Full traceback:")  # Add full traceback for debugging
            return {"topics": []}

    async def process_daily_memories(self, user_conversations):
        """Process and store daily user conversations with analysis."""
        try:
            logger.info("Starting daily memory processing...")
            
            # First analyze the conversations
            analysis = await self.analyze_daily_conversations(user_conversations)
            
            # Store only relevant analyzed topics
            stored_count = 0
            for topic in analysis.get('topics', []):
                if topic.get('relevant', False):
                    success = self.store_announcement_sync(topic.get('summary', ''))
                    if success:
                        stored_count += 1
            
            logger.info(f"Stored {stored_count} relevant memories from analysis")
            
            # Only store raw conversations if analysis failed (as backup)
            if not analysis.get('topics'):
                logger.warning("Analysis failed, storing raw conversations as backup")
                for user_id, conversations in user_conversations.items():
                    conversation_text = "\n".join([
                        f"{'Assistant' if msg['is_bot'] else 'User'}: {msg['content']}"
                        for msg in conversations
                    ])
                    self.store_announcement_sync(conversation_text)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing daily memories: {e}")
            raise

    def store_marketcap_sync(self, marketcap_memory: str) -> bool:
        """Store marketcap in memories table, replacing any existing marketcap memory"""
        try:
            # First, find and delete any existing marketcap memories
            # We'll search for memories that start with "Current marketcap:"
            existing_memories = self.db.client.table('memories')\
                .select('*')\
                .like('memory', 'Current marketcap:%')\
                .execute()
            
            if existing_memories.data:
                for mem in existing_memories.data:
                    self.db.client.table('memories')\
                        .delete()\
                        .eq('id', mem['id'])\
                        .execute()
            
            # Format memory data according to the actual table schema
            memory_data = {
                'memory': marketcap_memory,
                'created_at': datetime.now().isoformat()
            }
            
            # Use the standard insert_memory method
            success = self.db.insert_memory(memory_data)
            
            if success:
                logger.info(f"Successfully stored marketcap memory: {marketcap_memory}")
                return True
            
            logger.error("Failed to store marketcap memory")
            return False
            
        except Exception as e:
            logger.error(f"Error storing marketcap memory: {e}")
            logger.exception("Full traceback:")  # Added full traceback for better debugging
            return False