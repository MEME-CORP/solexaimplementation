import os
import json
import logging
from supabase import create_client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_memories():
    """Migrate memories from JSON file to Supabase database"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize Supabase client
        supabase = create_client(
            os.getenv('NEXT_PUBLIC_SUPABASE_URL'),
            os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')
        )
        
        # Read memories from JSON file - Updated path
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),  # Get project root
            'data',  # Go to data directory
            'memories.json'  # Target file
        )
        
        logger.info(f"Reading memories from: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            memories = data.get('memories', [])
        
        logger.info(f"Found {len(memories)} memories in JSON file")
        
        # Insert memories into database
        success_count = 0
        for memory in memories:
            try:
                response = supabase.table('memories').insert({
                    'memory': memory
                }).execute()
                success_count += 1
                logger.info(f"Migrated memory: {memory[:50]}...")
            except Exception as e:
                logger.error(f"Error inserting memory: {e}")
                continue
                
        logger.info(f"Migration completed. Successfully migrated {success_count} out of {len(memories)} memories")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    logger.info("Starting memory migration...")
    migrate_memories() 