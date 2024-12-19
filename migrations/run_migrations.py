import os
import logging
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    """Run all database migrations"""
    try:
        # Initialize Supabase client
        supabase = create_client(
            os.getenv('NEXT_PUBLIC_SUPABASE_URL'),
            os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')
        )
        
        # Read and execute create_memories_table.sql
        with open('migrations/create_memories_table.sql', 'r') as f:
            sql = f.read()
            supabase.query(sql).execute()
        
        logger.info("Created memories table")
        
        # Run memories migration
        from migrate_memories import migrate_memories
        migrate_memories()
        
        logger.info("All migrations completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == '__main__':
    run_migrations() 