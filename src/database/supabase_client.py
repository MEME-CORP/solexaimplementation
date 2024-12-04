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
        """Get current story circle data with all related data"""
        try:
            # Get the current active story circle
            story = self.client.table('story_circle')\
                .select('*')\
                .eq('is_current', True)\
                .single()\
                .execute()

            if not story.data:
                return self.create_story_circle()

            story_circle_id = story.data['id']

            # Get phases for this story circle
            phases = self.client.table('story_phases')\
                .select('*')\
                .eq('story_circle_id', story_circle_id)\
                .order('phase_number')\
                .execute()

            # Get events and dialogues
            events_dialogues = self.client.table('events_dialogues')\
                .select('*')\
                .eq('story_circle_id', story_circle_id)\
                .order('phase_number')\
                .order('id')\
                .execute()

            # Find current phase by looking at the earliest phase with no events
            all_phase_numbers = set(phase['phase_number'] for phase in phases.data)
            event_phase_numbers = set(event['phase_number'] for event in events_dialogues.data)
            incomplete_phases = sorted(all_phase_numbers - event_phase_numbers)
            
            current_phase_number = incomplete_phases[0] if incomplete_phases else 1
            current_phase = next(
                (phase['phase_name'] for phase in phases.data 
                 if phase['phase_number'] == current_phase_number),
                'You'  # Default to first phase if not found
            )

            # Get current event and dialogue
            current_events = [e for e in events_dialogues.data 
                             if e['phase_number'] == current_phase_number]
            current_event = current_events[0] if current_events else None

            # Structure the response
            return {
                "id": story_circle_id,
                "current_phase": current_phase,
                "current_phase_number": current_phase_number,
                "is_current": story.data['is_current'],
                "phases": [
                    {
                        "phase": phase['phase_name'],
                        "phase_number": phase['phase_number'],
                        "description": phase['phase_description']
                    }
                    for phase in phases.data
                ],
                "events": [ed['event'] for ed in events_dialogues.data],
                "dialogues": [ed['inner_dialogue'] for ed in events_dialogues.data],
                "dynamic_context": {
                    'current_event': current_event['event'] if current_event else '',
                    'current_inner_dialogue': current_event['inner_dialogue'] if current_event else '',
                    'next_event': current_events[1]['event'] if len(current_events) > 1 else ''
                }
            }

        except Exception as e:
            logger.error(f"Error fetching story circle: {e}")
            raise

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
            response = self.client.table('circle_memories').select('memory').execute()
            if response.data:
                return {"memories": [record['memory'] for record in response.data]}
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

    def create_story_circle(self):
        """Create a new story circle"""
        try:
            # Create new story circle entry with only is_current flag
            story = self.client.table('story_circle').insert({
                'is_current': True
            }).execute()

            story_circle_id = story.data[0]['id']

            # Create initial phases
            phase_order = ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]
            for i, phase_name in enumerate(phase_order, 1):
                self.client.table('story_phases').insert({
                    'story_circle_id': story_circle_id,
                    'phase_name': phase_name,
                    'phase_number': i,
                    'phase_description': ''
                }).execute()

            # Return initial story circle state
            return self.get_story_circle()

        except Exception as e:
            logger.error(f"Error creating story circle: {e}")
            raise

    def update_story_circle_state(self, story_circle):
        """Update story circle state including phases and events"""
        try:
            story_circle_id = story_circle['id']
            
            # Update main story circle data
            update_data = {
                'current_phase': story_circle['current_phase'],
                'current_phase_number': story_circle['current_phase_number']
            }
            self.client.table('story_circle').update(update_data).eq('id', story_circle_id).execute()
            
            # Update phases
            for phase in story_circle['phases']:
                self.client.table('story_phases').update({
                    'phase_description': phase['description']
                }).eq('story_circle_id', story_circle_id)\
                  .eq('phase_name', phase['phase'])\
                  .execute()
            
            # Get current phase number
            current_phase_number = story_circle['current_phase_number']
            
            # Clear existing events/dialogues for current phase
            self.client.table('events_dialogues')\
                .delete()\
                .eq('story_circle_id', story_circle_id)\
                .eq('phase_number', current_phase_number)\
                .execute()
            
            # Insert new events/dialogues for current phase
            events_dialogues = [
                {
                    'story_circle_id': story_circle_id,
                    'phase_number': current_phase_number,
                    'event': event,
                    'inner_dialogue': dialogue
                }
                for event, dialogue in zip(story_circle['events'], story_circle['dialogues'])
            ]
            
            for event_data in events_dialogues:
                self.client.table('events_dialogues').insert(event_data).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating story circle state: {e}")
            raise

    def insert_circle_memories(self, story_circle_id, memories):
        """Insert new memories for a completed story circle - synchronous"""
        try:
            self.client.table('circle_memories').insert({
                'story_circle_id': story_circle_id,
                'memory': memories
            }).execute()
        except Exception as e:
            logger.error(f"Error inserting circle memories: {e}")
            raise

    def get_circle_memories(self):
        """Get all circle memories"""
        try:
            # Get memories without ordering by created_at
            memories = self.client.table('circle_memories')\
                .select('memory')\
                .execute()
            
            if not memories.data:
                return {"memories": []}
            
            return {"memories": [m['memory'] for m in memories.data]}
        
        except Exception as e:
            logger.error(f"Error fetching circle memories: {e}")
            return {"memories": []}

    def update_story_circle(self, story_circle_id, updates):
        """Update specific story circle fields - synchronous"""
        try:
            self.client.table('story_circle')\
                .update(updates)\
                .eq('id', story_circle_id)\
                .execute()
        except Exception as e:
            logger.error(f"Error updating story circle: {e}")
            raise

    def get_story_phases(self):
        """Get phases for current story circle"""
        try:
            # Get current story circle id
            story = self.client.table('story_circle')\
                .select('id')\
                .eq('is_current', True)\
                .single()\
                .execute()
            
            if not story.data:
                return []
            
            # Get phases for this story circle
            phases = self.client.table('story_phases')\
                .select('*')\
                .eq('story_circle_id', story.data['id'])\
                .order('phase_number')\
                .execute()
            
            return phases.data
        
        except Exception as e:
            logger.error(f"Error fetching story phases: {e}")
            return []

    def get_events_dialogues(self):
        """Get events and dialogues for current story circle"""
        try:
            # Get current story circle id
            story = self.client.table('story_circle')\
                .select('id')\
                .eq('is_current', True)\
                .single()\
                .execute()
            
            if not story.data:
                return []
            
            # Get events for this story circle
            events = self.client.table('events_dialogues')\
                .select('*')\
                .eq('story_circle_id', story.data['id'])\
                .order('phase_number')\
                .order('id')\
                .execute()
            
            return events.data
        
        except Exception as e:
            logger.error(f"Error fetching events/dialogues: {e}")
            return []