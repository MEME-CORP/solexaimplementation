import json
import os
from supabase import create_client
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('migration')

def load_json_file(file_path):
    """Load and validate JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in file: {file_path}")
        return None

def migrate_data():
    """Migrate JSON data to Supabase database"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize Supabase client
        url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        key = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        
        if not url or not key:
            raise ValueError("Supabase credentials not found in environment variables")
        
        supabase = create_client(url, key)
        logger.info("Connected to Supabase")

        # Define data files to migrate
        data_files = {
            'memories': ('data/memories.json', 'memories'),
            'topics': ('data/topics.json', 'topics'),
            'emotion_formats': ('data/emotion_formats.json', 'formats'),
            'length_formats': ('data/length_formats.json', 'formats'),
            'processed_tweets': ('data/processed_tweets.txt', None)
        }

        # Migrate story circle data
        story_circle_data = load_json_file('data/story_circle.json')
        if story_circle_data:
            try:
                result = supabase.table('story_circle').insert({
                    'narrative': story_circle_data['narrative']
                }).execute()
                logger.info("Inserted story circle data successfully")
            except Exception as e:
                logger.error(f"Error inserting story circle data: {str(e)}")

        # Migrate circle memories data
        circle_memories_data = load_json_file('data/circle_memories.json')
        if circle_memories_data:
            try:
                result = supabase.table('circle_memories').insert({
                    'memories': circle_memories_data
                }).execute()
                logger.info("Inserted circle memories data successfully")
            except Exception as e:
                logger.error(f"Error inserting circle memories data: {str(e)}")

        # Add special handling for processed_tweets.txt
        try:
            with open('data/processed_tweets.txt', 'r') as f:
                tweet_ids = f.read().splitlines()
                
            # Prepare batch data for processed tweets
            batch_size = 50
            for i in range(0, len(tweet_ids), batch_size):
                batch = tweet_ids[i:i + batch_size]
                batch_data = [{'tweet_id': tweet_id} for tweet_id in batch]
                
                try:
                    result = supabase.table('processed_tweets').insert(batch_data).execute()
                    logger.info(f"Inserted {len(batch)} processed tweet IDs")
                except Exception as e:
                    logger.error(f"Error inserting processed tweets batch: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error processing processed_tweets.txt: {str(e)}")

        # Migrate each file
        for table_name, (file_path, key) in data_files.items():
            logger.info(f"Starting migration for {table_name}")
            
            # Load JSON data
            data = load_json_file(file_path)
            if not data:
                logger.error(f"Skipping {table_name} due to data loading error")
                continue

            items = data.get(key, [])
            
            # Insert data in batches
            batch_size = 50
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                try:
                    # Prepare batch data according to table structure
                    if table_name == 'memories' or table_name == 'circle_memories':
                        batch_data = [{'content': item} for item in batch]
                    elif table_name == 'topics':
                        batch_data = [{'topic': item['topic']} for item in batch]
                    else:  # emotion_formats and length_formats
                        batch_data = [{'format': item['format'], 
                                     'description': item['description']} 
                                    for item in batch]

                    # Insert batch
                    result = supabase.table(table_name).insert(batch_data).execute()
                    logger.info(f"Inserted {len(batch)} records into {table_name}")
                    
                except Exception as e:
                    logger.error(f"Error inserting batch into {table_name}: {str(e)}")

        logger.info("Migration completed successfully")

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        migrate_data()
    except Exception as e:
        logger.error(f"Migration script failed: {str(e)}")
