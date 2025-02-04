import unittest
import json
import os
import pandas as pd
from datetime import datetime
from src.story_circle_manager import StoryCircleManager

class TestStoryCircleLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize test environment"""
        cls.base_path = os.path.dirname(os.path.abspath(__file__))
        cls.project_root = os.path.dirname(cls.base_path)
        cls.test_data_path = os.path.join(cls.base_path, 'data')
        cls.csv_path = os.path.join(cls.project_root, 'data', 'story_circles.csv')
        
        # Create test CSV if it doesn't exist
        if not os.path.exists(cls.csv_path):
            df = pd.DataFrame(columns=['id', 'datetime', 'story_circle', 'status'])
            df.to_csv(cls.csv_path, index=False)
        
        cls.manager = StoryCircleManager()
        
        # Sample story circle for testing
        cls.sample_story_circle = {
            "narrative": {
                "current_story_circle": [
                    {
                        "phase": "You",
                        "description": "Test description",
                        "events": ["Event 1", "Event 2"],
                        "inner_dialogues": ["Dialogue 1", "Dialogue 2"]
                    }
                    # ... other phases would be here in real data
                ],
                "current_phase": "You",
                "next_phase": "Need"
            }
        }

    def setUp(self):
        """Reset the CSV before each test"""
        df = pd.DataFrame(columns=['id', 'datetime', 'story_circle', 'status'])
        df.to_csv(self.csv_path, index=False)

    def test_save_story_circle(self):
        """Test saving a story circle to CSV"""
        story_id = self.manager.save_story_circle(self.sample_story_circle)
        
        # Verify save
        self.assertIsNotNone(story_id)
        df = pd.read_csv(self.csv_path)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['id'], story_id)
        self.assertEqual(df.iloc[0]['status'], 'active')
        
        # Verify stored story circle
        stored_circle = json.loads(df.iloc[0]['story_circle'])
        self.assertEqual(stored_circle['narrative']['current_phase'], 'You')
        self.assertEqual(stored_circle['narrative']['next_phase'], 'Need')

    def test_advance_phase(self):
        """Test advancing through story circle phases"""
        # Save initial story circle
        story_id = self.manager.save_story_circle(self.sample_story_circle)
        
        # Test phase advancement
        updated_circle = self.manager.advance_phase(story_id)
        
        # Verify phase update
        self.assertEqual(updated_circle['narrative']['current_phase'], 'Need')
        self.assertEqual(updated_circle['narrative']['next_phase'], 'Go')
        
        # Verify in CSV
        df = pd.read_csv(self.csv_path)
        stored_circle = json.loads(df.iloc[0]['story_circle'])
        self.assertEqual(stored_circle['narrative']['current_phase'], 'Need')
        self.assertEqual(stored_circle['narrative']['next_phase'], 'Go')

    def test_complete_story_circle(self):
        """Test completing a full story circle"""
        # Save initial story circle
        story_id = self.manager.save_story_circle(self.sample_story_circle)
        
        # Advance through all phases
        phases = ['You', 'Need', 'Go', 'Search', 'Find', 'Take', 'Return', 'Change']
        current_circle = self.sample_story_circle
        
        for i in range(len(phases) - 1):  # -1 because we start at 'You'
            current_circle = self.manager.advance_phase(story_id)
            self.assertEqual(current_circle['narrative']['current_phase'], phases[i + 1])
            
            if i < len(phases) - 2:
                self.assertEqual(current_circle['narrative']['next_phase'], phases[i + 2])
        
        # Advance one more time to complete the circle
        final_circle = self.manager.advance_phase(story_id)
        
        # Verify circle completion
        df = pd.read_csv(self.csv_path)
        self.assertEqual(df.iloc[0]['status'], 'inactive')
        
        # Verify new circle started
        self.assertEqual(len(df), 2)  # Should have both old and new circles
        new_circle = json.loads(df.iloc[1]['story_circle'])
        self.assertEqual(new_circle['narrative']['current_phase'], 'You')
        self.assertEqual(new_circle['narrative']['next_phase'], 'Need')

    def test_get_last_inactive_story_circle(self):
        """Test retrieving the last inactive story circle"""
        # Save two story circles
        story_id1 = self.manager.save_story_circle(self.sample_story_circle)
        story_id2 = self.manager.save_story_circle(self.sample_story_circle)
        
        # Mark first one as inactive
        df = pd.read_csv(self.csv_path)
        df.loc[df['id'] == story_id1, 'status'] = 'inactive'
        df.to_csv(self.csv_path, index=False)
        
        # Get last inactive circle
        inactive_circle = self.manager.get_last_inactive_story_circle()
        
        # Verify retrieval
        self.assertIsNotNone(inactive_circle)
        self.assertEqual(inactive_circle['narrative']['current_phase'], 'You')

if __name__ == '__main__':
    unittest.main(verbosity=2) 