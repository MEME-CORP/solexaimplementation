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
            return prompt_config['memory_analysis_prompt']
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
            
            logger.info(f"Successfully stored memory in database: {announcement[:100]}...")
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