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
        """Get current story circle data with its phases"""
        try:
            # Get the latest story circle
            story = self.client.table('story_circle')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()

            if not story.data:
                # Return default structure if no data exists
                return {
                    "narrative": {
                        "events": [],
                        "next_phase": "Need",
                        "current_phase": "You",
                        "dynamic_context": {
                            "next_event": "",
                            "current_event": "",
                            "current_inner_dialogue": ""
                        },
                        "inner_dialogues": [],
                        "current_story_circle": [
                            {"phase": phase, "description": ""} 
                            for phase in ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]
                        ]
                    }
                }

            story_data = story.data[0]

            # Get associated phases
            phases = self.client.table('story_phases')\
                .select('*')\
                .eq('story_circle_id', story_data['id'])\
                .execute()

            # Reconstruct the full story circle structure
            narrative = story_data['narrative']
            
            # If no phases exist, create default phase structure
            if not phases.data:
                narrative['current_story_circle'] = [
                    {"phase": phase, "description": ""} 
                    for phase in ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]
                ]
            else:
                # Sort phases in correct order
                phase_order = ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]
                phase_dict = {phase['phase']: phase['description'] for phase in phases.data}
                narrative['current_story_circle'] = [
                    {"phase": phase, "description": phase_dict.get(phase, "")}
                    for phase in phase_order
                ]

            return {'narrative': narrative}

        except Exception as e:
            logger.error(f"Error fetching story circle: {e}")
            return None

    def update_story_circle(self, story_circle):
        """Update story circle and its phases"""
        try:
            if 'narrative' not in story_circle:
                story_circle = {'narrative': story_circle}

            narrative = story_circle['narrative']
            
            # Validate required fields
            required_fields = ['events', 'next_phase', 'current_phase', 'dynamic_context', 
                             'inner_dialogues', 'current_story_circle']
            
            for field in required_fields:
                if field not in narrative:
                    logger.error(f"Missing required field in story circle: {field}")
                    return False

            # Save main story circle data
            result = self.client.table('story_circle').insert({
                'narrative': {
                    'events': narrative['events'],
                    'next_phase': narrative['next_phase'],
                    'current_phase': narrative['current_phase'],
                    'dynamic_context': narrative['dynamic_context'],
                    'inner_dialogues': narrative['inner_dialogues']
                }
            }).execute()

            if not result.data:
                logger.error("Failed to save story circle")
                return False

            story_circle_id = result.data[0]['id']

            # Save phases
            for phase in narrative['current_story_circle']:
                self.client.table('story_phases').insert({
                    'story_circle_id': story_circle_id,
                    'phase': phase['phase'],
                    'description': phase['description']
                }).execute()

            return True

        except Exception as e:
            logger.error(f"Error updating story circle: {e}")
            return False

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