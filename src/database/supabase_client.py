# src/database/supabase_client.py
from supabase import create_client
from src.config import Config
import logging
import json

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

            # Get current phase
            current_phase = next(
                (phase for phase in phases.data if phase.get('is_current', False)),
                phases.data[0] if phases.data else None
            )
            
            if not current_phase:
                current_phase = phases.data[0] if phases.data else None
                current_phase_number = 1
            else:
                current_phase_number = current_phase['phase_number']

            # Get events and dialogues
            events_dialogues = self.client.table('events_dialogues')\
                .select('*')\
                .eq('story_circle_id', story_circle_id)\
                .eq('phase_number', current_phase_number)\
                .order('id')\
                .execute()

            # Structure the response
            return {
                "id": story_circle_id,
                "current_phase": current_phase['phase_name'] if current_phase else 'You',
                "current_phase_number": current_phase_number,
                "is_current": story.data['is_current'],
                "phases": [
                    {
                        "phase": phase['phase_name'],
                        "phase_number": phase['phase_number'],
                        "description": phase['phase_description'] or (
                            "Fwog enjoys the serene simplicity of their little pond, surrounded by lush greenery and the gentle hum of nature." 
                            if phase['phase_name'] == 'You' and phase['phase_number'] == 1 
                            else ""
                        )
                    }
                    for phase in phases.data
                ],
                "events": [ed['event'] for ed in events_dialogues.data],
                "dialogues": [ed['inner_dialogue'] for ed in events_dialogues.data],
                "dynamic_context": {
                    'current_event': events_dialogues.data[0]['event'] if events_dialogues.data else '',
                    'current_inner_dialogue': events_dialogues.data[0]['inner_dialogue'] if events_dialogues.data else '',
                    'next_event': events_dialogues.data[1]['event'] if len(events_dialogues.data) > 1 else ''
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
            
            # Update only the is_current flag in main story circle table
            update_data = {
                'is_current': story_circle.get('is_current', True)
            }
            
            logger.info(f"Updating story circle with data: {json.dumps(update_data, indent=2)}")
            
            # Update the story circle
            self.client.table('story_circle')\
                .update(update_data)\
                .eq('id', story_circle_id)\
                .execute()
            
            # Update phases without is_current flag
            for phase in story_circle['phases']:
                self.client.table('story_phases').update({
                    'phase_name': phase['phase'],
                    'phase_number': phase['phase_number'],
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
            
            # Insert new events/dialogues for current phase with event_order
            events_dialogues = [
                {
                    'story_circle_id': story_circle_id,
                    'phase_number': current_phase_number,
                    'event': event,
                    'inner_dialogue': dialogue,
                    'event_order': idx + 1  # Add event_order starting from 1
                }
                for idx, (event, dialogue) in enumerate(zip(story_circle['events'], story_circle['dialogues']))
            ]
            
            # Log the events being inserted
            logger.debug(f"Inserting events/dialogues: {json.dumps(events_dialogues, indent=2)}")
            
            # Insert events one by one to better handle any errors
            for event_data in events_dialogues:
                try:
                    self.client.table('events_dialogues').insert(event_data).execute()
                    logger.debug(f"Successfully inserted event {event_data['event_order']}")
                except Exception as e:
                    logger.error(f"Error inserting event {event_data['event_order']}: {e}")
                    raise
            
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

    def get_story_phases(self, story_circle_id=None):
        """Get phases for story circle. If no ID provided, gets phases for current story circle"""
        try:
            if story_circle_id is None:
                # Get current story circle id
                story = self.client.table('story_circle')\
                    .select('id')\
                    .eq('is_current', True)\
                    .single()\
                    .execute()
                
                if not story.data:
                    logger.error("No current story circle found")
                    return []
                
                story_circle_id = story.data['id']
            
            # Get phases for this story circle
            phases = self.client.table('story_phases')\
                .select('*')\
                .eq('story_circle_id', story_circle_id)\
                .order('phase_number')\
                .execute()
            
            return phases.data
        
        except Exception as e:
            logger.error(f"Error fetching story phases: {e}")
            return []

    def get_events_dialogues(self, story_circle_id, phase_number):
        """Get events and dialogues for a phase, ordered by event_order"""
        try:
            query = self.client.table('events_dialogues')\
                .select('*')\
                .eq('story_circle_id', story_circle_id)\
                .eq('phase_number', phase_number)\
                .order('event_order')
            
            result = query.execute()
            
            if not result.data:
                logger.warning(f"No events found for story_circle_id={story_circle_id}, phase={phase_number}")
                return []
            
            logger.info(f"Retrieved {len(result.data)} events in order")
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting events and dialogues: {e}")
            logger.error(f"Parameters: story_circle_id={story_circle_id}, phase_number={phase_number}")
            logger.exception("Full traceback:")
            return []

    def update_phase_description(self, story_circle_id: int, phase_name: str, description: str) -> bool:
        """Update a specific phase description"""
        try:
            # Log the update attempt
            logger.info(f"Updating phase description for story_circle_id={story_circle_id}, phase={phase_name}")
            logger.debug(f"New description: {description}")
            
            response = self.client.table('story_phases')\
                .update({'phase_description': description})\
                .eq('story_circle_id', story_circle_id)\
                .eq('phase_name', phase_name)\
                .execute()
            
            success = bool(response.data)
            if success:
                logger.info("Phase description updated successfully")
            else:
                logger.warning("No phase was updated - check if phase exists")
                
            return success
            
        except Exception as e:
            logger.error(f"Error updating story phase: {e}")
            logger.exception("Full traceback:")
            return False