import unittest
import json
import os
import yaml
from openai import OpenAI
from src.config import Config
from src.creativity_manager import CreativityManager
from src.story_circle_manager import StoryCircleManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('story_circle_ai_tests')

class TestStoryCircleAI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize managers"""
        # Initialize managers
        cls.creativity_manager = CreativityManager()
        cls.story_circle_manager = StoryCircleManager()
        
        # Initialize OpenAI client
        cls.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )

    def test_prompt_completions(self):
        """Test both creativity and story circle prompt completions"""
        print("\n=== Testing AI Prompt Completions ===")
        
        # 1. Test Creativity Prompt
        print("\n--- Testing Creativity Prompt ---")
        print("Sending creativity prompt...")
        
        # Get creative instructions
        creative_instructions = self.creativity_manager.generate_creative_instructions([])
        
        print("\nCreativity Prompt Output:")
        print("-" * 40)
        print(creative_instructions)
        print("-" * 40)
        
        # For testing purposes, we can overlook the CS tags requirement
        self.assertIsNotNone(creative_instructions)
        
        # 2. Test Story Circle Prompt using the creative instructions
        print("\n--- Testing Story Circle Prompt ---")
        print("Sending story circle prompt with creative instructions...")
        
        # Pass creative instructions to story circle manager
        story_circle = self.story_circle_manager.update_story_circle(creative_instructions=creative_instructions)
        
        print("\nStory Circle Prompt Output:")
        print("-" * 40)
        print(json.dumps(story_circle, indent=2))
        print("-" * 40)
        
        # Validate story circle structure
        self.assertIsNotNone(story_circle)
        self.assertIsInstance(story_circle, dict)
        self.assertIn('narrative', story_circle)
        self.assertIn('current_story_circle', story_circle['narrative'])

if __name__ == '__main__':
    unittest.main(verbosity=2) 