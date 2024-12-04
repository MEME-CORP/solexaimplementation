import os
import sys
import logging

# Get the absolute path to the project root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# Add the project root to the Python path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.database.supabase_client import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('database_clear')

def clear_database():
    """Clear all data from the database tables in the correct order"""
    try:
        db = DatabaseService()
        logger.info("Starting database clear...")

        # Clear tables in order (child tables first to respect foreign key constraints)
        tables = [
            'events_dialogues',
            'circle_memories',
            'story_phases',
            'story_circle'
        ]

        for table in tables:
            logger.info(f"Clearing table: {table}")
            # Delete all records with an explicit filter that will match everything
            result = db.client.table(table).delete().filter('id', 'gte', 0).execute()
            logger.info(f"Cleared {table}")

        logger.info("Successfully cleared all tables!")
        return True

    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        return False

if __name__ == "__main__":
    clear_database()