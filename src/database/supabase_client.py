# src/database/supabase_client.py
from supabase import create_client
from src.config import Config
import logging

logger = logging.getLogger('database')

class DatabaseService:
    def __init__(self):
        self.client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_KEY
        )

    def get_memories(self):
        """Get all memories including circle memories synchronously"""
        try:
            # Get regular memories
            memories_response = self.client.table('memories').select('content').execute()
            memories = [record['content'] for record in memories_response.data]
            
            # Get circle memories
            circle_response = self.client.table('circle_memories').select('memories').execute()
            if circle_response.data:
                circle_memories = circle_response.data[0]['memories']['memories']
                memories.extend(circle_memories)
            
            return memories
        except Exception as e:
            logger.error(f"Error fetching memories: {e}")
            return []

    def get_story_circle(self):
        """Get current story circle data - unified method for all components"""
        try:
            response = self.client.table('story_circle').select('narrative').execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching story circle: {e}")
            return None

    # Alias for backward compatibility
    get_story_circle_sync = get_story_circle

    def get_circle_memories_sync(self):
        """Get circle memories synchronously"""
        try:
            response = self.client.table('circle_memories').select('memories').execute()
            if response.data:
                return response.data[0]['memories']
            return {"memories": []}
        except Exception as e:
            logger.error(f"Error fetching circle memories synchronously: {e}")
            return {"memories": []}

    def update_story_circle(self, story_circle):
        """Update story circle in database - unified method for all components"""
        try:
            self.client.table('story_circle').upsert({
                'narrative': story_circle['narrative']
            }).execute()
        except Exception as e:
            logger.error(f"Error updating story circle: {e}")
            raise

    def update_circle_memories(self, circles_memory):
        """Update circle memories in database - unified method"""
        try:
            self.client.table('circle_memories').upsert({
                'memories': circles_memory
            }).execute()
        except Exception as e:
            logger.error(f"Error updating circle memories: {e}")
            raise

    def get_topics(self):
        """Get all topics"""
        try:
            response = self.client.table('topics').select('topic').execute()
            return [{'topic': record['topic']} for record in response.data]
        except Exception as e:
            logger.error(f"Error fetching topics: {e}")
            return []

    def get_emotion_formats(self):
        """Get all emotion formats"""
        try:
            response = self.client.table('emotion_formats').select('*').execute()
            return [{'format': record['format'], 'description': record['description']} 
                   for record in response.data]
        except Exception as e:
            logger.error(f"Error fetching emotion formats: {e}")
            return []

    def get_length_formats(self):
        """Get all length formats"""
        try:
            response = self.client.table('length_formats').select('*').execute()
            return [{'format': record['format'], 'description': record['description']} 
                   for record in response.data]
        except Exception as e:
            logger.error(f"Error fetching length formats: {e}")
            return []

    def get_processed_tweets(self):
        """Get all processed tweet IDs"""
        try:
            response = self.client.table('processed_tweets').select('tweet_id').execute()
            return [record['tweet_id'] for record in response.data]
        except Exception as e:
            logger.error(f"Error fetching processed tweets: {e}")
            return []

    def add_memories(self, new_memories):
        """Add new memories to database"""
        try:
            memory_records = [{'content': memory} for memory in new_memories]
            self.client.table('memories').insert(memory_records).execute()
        except Exception as e:
            logger.error(f"Error adding memories: {e}")
            raise