import sys
import os
from pathlib import Path
import logging
from src.database.supabase_client import DatabaseService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('memory_uploader')

def read_memories_file(file_path):
    """Read memories from the specified file"""
    try:
        # Specify UTF-8 encoding when opening the file
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read lines and remove empty lines and leading/trailing whitespace
            memories = [line.strip() for line in f.readlines() if line.strip()]
            
            logger.info(f"Successfully read {len(memories)} memories from file")
            return memories
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error reading file: {e}. Trying with different encoding...")
        try:
            # Fallback to latin-1 if UTF-8 fails
            with open(file_path, 'r', encoding='latin-1') as f:
                memories = [line.strip() for line in f.readlines() if line.strip()]
                logger.info(f"Successfully read {len(memories)} memories using latin-1 encoding")
                return memories
        except Exception as e2:
            logger.error(f"Failed to read file with alternative encoding: {e2}")
            return None
    except Exception as e:
        logger.error(f"Error reading memories file: {e}")
        return None

def upload_memories():
    """Upload memories from new_memories.txt to Supabase database"""
    try:
        # Get the project root directory
        project_root = Path(__file__).parent.parent.parent
        memories_file = project_root / 'data' / 'new_memories.txt'

        # Read memories
        memories = read_memories_file(memories_file)
        if not memories:
            logger.error("No memories found or error reading file")
            return False

        # Initialize database service
        db = DatabaseService()

        # Upload memories
        logger.info(f"Uploading {len(memories)} memories to database...")
        db.add_memories(memories)
        
        logger.info("Successfully uploaded memories to database")
        return True

    except Exception as e:
        logger.error(f"Error in upload_memories: {e}")
        return False

if __name__ == "__main__":
    success = upload_memories()
    sys.exit(0 if success else 1) 