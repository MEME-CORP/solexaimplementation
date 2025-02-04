import unittest
import json
import os
import yaml
from openai import OpenAI
from src.config import Config
from src.creativity_manager import CreativityManager
from src.story_circle_manager import StoryCircleManager
import logging
import pandas as pd
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('story_circle_ai_tests')

class TestStoryCircleAI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize managers and paths"""
        # Initialize managers
        cls.creativity_manager = CreativityManager()
        cls.story_circle_manager = StoryCircleManager()
        
        # Initialize OpenAI client
        cls.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        
        # Get CSV path
        cls.csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'story_circles.csv')

    def setUp(self):
        """Reset CSV and prepare test environment"""
        # Reset CSV
        df = pd.DataFrame(columns=['id', 'datetime', 'story_circle', 'status', 'current_phase', 'next_phase'])
        df.to_csv(self.csv_path, index=False)
        
        # Setup logging file
        self.log_file = os.path.join(os.path.dirname(__file__), 'data', 'ai_interactions.jsonl')
        if os.path.exists(self.log_file):
            os.remove(self.log_file)

    def _log_interaction(self, interaction_type, input_data, output_data, cleaned_output=None):
        """Log AI interaction in a readable format"""
        log_entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'interaction_type': interaction_type,
            'input': input_data,
            'output': output_data,
            'cleaned_output': cleaned_output
        }
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Write in pretty format
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, indent=2) + '\n\n')  # Add extra newline for readability

    def test_full_story_circle_flow(self):
        """Test complete story circle flow with AI integration"""
        print("\n=== Testing Full Story Circle Flow ===")
        
        # 1. Generate first story circle
        print("\n--- Generating First Story Circle ---")
        creative_instructions = self.creativity_manager.generate_creative_instructions([])
        self.assertIsNotNone(creative_instructions)
        print("Creative instructions generated")
        
        # Log creativity instructions
        self._log_interaction(
            'creativity_instructions',
            {'prompt': 'Generate creative instructions'},
            creative_instructions
        )
        
        story_circle = self.story_circle_manager.update_story_circle(creative_instructions)
        self.assertIsNotNone(story_circle)
        print("Initial story circle generated")
        
        # Log story circle generation
        self._log_interaction(
            'story_circle_generation',
            {'creative_instructions': creative_instructions},
            story_circle,
            json.dumps(story_circle, indent=2)
        )
        
        # Get the story circle ID
        df = pd.read_csv(self.csv_path)
        story_id = df.iloc[0]['id']
        
        # 2. Advance through all phases
        print("\n--- Advancing Through Phases ---")
        phases = ['You', 'Need', 'Go', 'Search', 'Find', 'Take', 'Return', 'Change']
        
        for i, phase in enumerate(phases):
            current_circle = self.story_circle_manager.advance_phase(story_id)
            self.assertIsNotNone(current_circle)
            
            # Read current phase from CSV
            df = pd.read_csv(self.csv_path)
            current_row = df[df['id'] == story_id].iloc[0]
            
            if i < len(phases) - 1:
                print(f"Advanced to phase: {current_row['current_phase']}")
                self.assertEqual(current_row['current_phase'], phases[(i + 1) % len(phases)])
                self.assertEqual(current_row['next_phase'], phases[(i + 2) % len(phases)])
            else:
                print("\n--- Starting New Story Circle ---")
                # Verify first circle is inactive
                self.assertEqual(current_row['status'], 'inactive')
                
                # Verify new circle is created and active
                self.assertEqual(len(df), 2)
                new_circle_row = df[df['status'] == 'active'].iloc[0]
                self.assertEqual(new_circle_row['current_phase'], 'You')
                self.assertEqual(new_circle_row['next_phase'], 'Need')
                print("New story circle created successfully")

if __name__ == '__main__':
    unittest.main(verbosity=2) 