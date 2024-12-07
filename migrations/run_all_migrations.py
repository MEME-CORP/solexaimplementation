import logging
from add_narrative_column import migrate_narrative_column
from story_circle_supabase_migration import migrate_story_circle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('migrations')

def run_all_migrations():
    """Run all migrations in the correct order"""
    try:
        # 1. Add narrative column
        if not migrate_narrative_column():
            logger.error("Failed to add narrative column")
            return False
            
        # 2. Run main story circle migration
        if not migrate_story_circle():
            logger.error("Failed to run story circle migration")
            return False
            
        logger.info("All migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        return False

if __name__ == "__main__":
    run_all_migrations() 