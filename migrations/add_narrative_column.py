import os
import sys
import logging
from supabase import create_client, Client

# Add the project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.config import Config

logger = logging.getLogger('migration')

def migrate_narrative_column():
    """Add narrative column to story_circle table"""
    try:
        # Initialize Supabase client
        supabase: Client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_KEY
        )
        
        # First, check if any rows exist
        result = supabase.table('story_circle').select("*").execute()
        
        if not result.data:
            logger.info("No existing rows found, creating initial row...")
            # Create initial row with narrative structure
            supabase.table('story_circle').insert({
                "is_current": True,
                "narrative": {
                    "current_story_circle": [],
                    "current_phase": "You",
                    "next_phase": "Need",
                    "events": [],
                    "inner_dialogues": [],
                    "dynamic_context": {
                        "current_event": "",
                        "current_inner_dialogue": "",
                        "next_event": ""
                    }
                }
            }).execute()
            logger.info("Created initial row with narrative structure")
            return True
            
        # If rows exist, update them one by one
        logger.info(f"Found {len(result.data)} existing rows to update")
        
        for row in result.data:
            try:
                # Update each row individually with proper WHERE clause
                supabase.table('story_circle')\
                    .update({
                        "narrative": {
                            "current_story_circle": [],
                            "current_phase": "You",
                            "next_phase": "Need",
                            "events": [],
                            "inner_dialogues": [],
                            "dynamic_context": {
                                "current_event": "",
                                "current_inner_dialogue": "",
                                "next_event": ""
                            }
                        }
                    })\
                    .eq('id', row['id'])\
                    .execute()
                logger.info(f"Updated row with id {row['id']}")
                
            except Exception as e:
                logger.error(f"Error updating row {row['id']}: {e}")
                continue
        
        logger.info("Successfully completed narrative column migration")
        return True
        
    except Exception as e:
        logger.error(f"Error during narrative column migration: {e}")
        logger.exception("Full traceback:")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = migrate_narrative_column()
    if success:
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed")
        sys.exit(1) 