"""
Integration tests for the Story Circle functionality.
These tests verify the complete story circle workflow including phase transitions
and event progression.
"""

import os
import sys
import json
import logging
from datetime import datetime
import pytest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_story_circle.log')
    ]
)
logger = logging.getLogger('test_story_circle')

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.story_circle_manager import StoryCircleManager
    from src.database.supabase_client import DatabaseService
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure you're running tests from the project root directory")
    raise

@pytest.fixture(scope="module")
def story_manager():
    """Fixture to provide StoryCircleManager instance"""
    logger.info("Initializing StoryCircleManager fixture")
    manager = StoryCircleManager()
    yield manager
    logger.info("Cleaning up StoryCircleManager fixture")

@pytest.fixture(scope="module")
def db_service():
    """Fixture to provide DatabaseService instance"""
    logger.info("Initializing DatabaseService fixture")
    service = DatabaseService()
    yield service
    logger.info("Cleaning up DatabaseService fixture")

class TestStoryCircleIntegration:
    """Integration tests for story circle progression"""
    
    def setup_method(self, method):
        """Setup test environment before each test - can be called directly"""
        logger.info("=== Setting up test environment ===")
        self.db = DatabaseService()
        self.story_manager = StoryCircleManager()
        self.expected_phases = ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]

    def teardown_method(self, method):
        """Cleanup after each test"""
        try:
            logger.info("=== Cleaning up test environment ===")
            # Clean up test story circles
            self.db.client.table('story_circle')\
                .delete()\
                .execute()
            # Clean up events and dialogues
            self.db.client.table('events_dialogues')\
                .delete()\
                .execute()
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")

    def test_story_circle_creation(self):
        """Test creation of new story circle"""
        logger.info("=== Testing Story Circle Creation ===")
        try:
            story_circle = self.db.create_story_circle()
            logger.info(f"Created story circle: {json.dumps(story_circle, indent=2)}")
            
            assert story_circle is not None, "Story circle should not be None"
            assert 'id' in story_circle, "Story circle should have an ID"
            assert story_circle.get('is_current') is True, "New story circle should be current"
            
            logger.info("Story circle creation test passed")
            return story_circle
            
        except Exception as e:
            logger.error(f"Error in story circle creation test: {e}")
            logger.exception("Full traceback:")
            raise

    def test_event_progression(self):
        """Test progression through events in a phase"""
        logger.info("=== Testing Event Progression ===")
        try:
            story_circle = self.story_manager.load_story_circle()
            logger.info(f"Loaded story circle: {json.dumps(story_circle, indent=2)}")
            
            if not story_circle.get('events'):
                story_circle = self.story_manager.update_story_circle()
            
            assert story_circle is not None, "Story circle should not be None"
            assert 'current_phase' in story_circle, "Story circle should have a current phase"
            
            # Test event progression
            updated_circle = self.story_manager.progress_narrative()
            logger.info(f"Updated story circle after progression: {json.dumps(updated_circle, indent=2)}")
            
            assert updated_circle is not None, "Updated story circle should not be None"
            assert updated_circle.get('events'), "Story circle should have events after progression"
            
            logger.info("Event progression test passed")
            return story_circle
            
        except Exception as e:
            logger.error(f"Error in event progression test: {e}")
            logger.exception("Full traceback:")
            raise

    def test_phase_transition(self):
        """Test transition between phases"""
        try:
            logger.info("=== Testing Phase Transition ===")
            
            story_circle = self.story_manager.load_story_circle()
            initial_phase = story_circle['current_phase']
            initial_phase_idx = self.expected_phases.index(initial_phase)
            
            logger.info(f"Initial phase: {initial_phase}")
            
            while True:
                story_circle = self.story_manager.progress_to_next_event(story_circle)
                if story_circle['current_phase'] != initial_phase:
                    break
            
            new_phase = story_circle['current_phase']
            expected_phase = self.expected_phases[(initial_phase_idx + 1) % len(self.expected_phases)]
            
            logger.info(f"Transitioned to phase: {new_phase}")
            assert new_phase == expected_phase, f"Expected phase {expected_phase}, got {new_phase}"
            assert self.db.verify_story_circle_state(story_circle), "Story circle state invalid after phase transition"
            
            return story_circle
            
        except Exception as e:
            logger.error(f"Error in phase transition test: {e}")
            logger.exception("Full traceback:")
            raise

    def test_story_circle_completion(self):
        """Test completion of entire story circle"""
        try:
            logger.info("=== Testing Story Circle Completion ===")
            
            story_circle = self.story_manager.load_story_circle()
            initial_id = story_circle['id']
            
            logger.info(f"Starting story circle ID: {initial_id}")
            
            phase_count = 0
            max_iterations = 100
            iterations = 0
            
            while phase_count < len(self.expected_phases) and iterations < max_iterations:
                iterations += 1
                current_phase = story_circle['current_phase']
                logger.info(f"Processing phase: {current_phase}")
                
                story_circle = self.story_manager.progress_to_next_event(story_circle)
                
                if story_circle['current_phase'] != current_phase:
                    phase_count += 1
                    logger.info(f"Completed phase {current_phase}, moved to {story_circle['current_phase']}")
                
                assert self.db.verify_story_circle_state(story_circle), f"Invalid state after iteration {iterations}"
            
            assert iterations < max_iterations, "Exceeded maximum iterations"
            assert story_circle['id'] != initial_id, "New story circle should have been created"
            
            memories = self.db.get_circle_memories()
            assert memories is not None, "Circle memories should exist"
            assert len(memories['memories']) > 0, "Should have at least one memory"
            
            logger.info(f"Story circle completed in {iterations} iterations")
            logger.info(f"Final memories: {json.dumps(memories, indent=2)}")
            
            return story_circle
            
        except Exception as e:
            logger.error(f"Error in story circle completion test: {e}")
            logger.exception("Full traceback:")
            raise

    def test_state_synchronization(self):
        """Test database state synchronization"""
        try:
            logger.info("=== Testing State Synchronization ===")
            
            story_circle = self.story_manager.load_story_circle()
            
            modified_circle = story_circle.copy()
            modified_circle['dynamic_context']['current_event'] = "Modified event"
            
            synced_circle = self.db.sync_story_circle(modified_circle)
            
            assert synced_circle is not None, "Synced circle should not be None"
            assert self.db.verify_story_circle_state(synced_circle), "Synced state should be valid"
            
            db_state = self.db.get_story_circle()
            assert self.db._states_match(synced_circle, db_state), "Synced state should match database"
            
            logger.info("State synchronization successful")
            
            return synced_circle
            
        except Exception as e:
            logger.error(f"Error in state synchronization test: {e}")
            logger.exception("Full traceback:")
            raise

    @pytest.mark.asyncio
    async def test_async_operations(self):
        """Test asynchronous story circle operations"""
        try:
            logger.info("=== Testing Async Operations ===")
            
            # Get narrative and verify structure
            narrative = self.story_manager.get_current_narrative()
            assert narrative is not None, "Narrative should not be None"
            assert "narrative" in narrative, "Narrative should have narrative key"
            assert "current_story_circle" in narrative["narrative"], "Narrative should have current_story_circle"
            
            # Get events and verify
            story_circle = self.story_manager.load_story_circle()
            events = self.db.get_events_dialogues(
                story_circle['id'],
                story_circle['current_phase_number']
            )
            assert events is not None, "Events should not be None"
            
            logger.info(f"Retrieved {len(events)} events")
            
            return narrative, events
            
        except Exception as e:
            logger.error(f"Error in async operations test: {e}")
            logger.exception("Full traceback:")
            raise

def run_all_tests():
    """Run all tests in sequence"""
    try:
        logger.info("=== Starting Story Circle Integration Tests ===")
        
        test = TestStoryCircleIntegration()
        test.setup_method(None)
        
        try:
            story_circle = test.test_story_circle_creation()
            story_circle = test.test_event_progression()
            story_circle = test.test_phase_transition()
            story_circle = test.test_story_circle_completion()
            story_circle = test.test_state_synchronization()
            
            logger.info("=== All tests completed successfully ===")
            
        finally:
            test.teardown_method(None)
        
    except Exception as e:
        logger.error("Test sequence failed")
        logger.exception("Full traceback:")
        raise

if __name__ == "__main__":
    run_all_tests()
 