import unittest
import json
import os
import yaml
import re
from typing import Dict, List, Optional
from pprint import pprint

class TestStoryCircleLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load test data and prompts"""
        # Get the project root directory (going up from test directory)
        cls.base_path = os.path.dirname(os.path.abspath(__file__))
        cls.project_root = os.path.dirname(cls.base_path)
        
        # Define paths
        cls.prompts_path = os.path.join(cls.project_root, 'src', 'prompts_config')
        cls.test_data_path = os.path.join(cls.base_path, 'data')
        
        # Ensure test data directory exists
        if not os.path.exists(cls.test_data_path):
            os.makedirs(cls.test_data_path)
        
        # Load test outputs
        test_outputs_path = os.path.join(cls.test_data_path, 'test_outputs.json')
        if not os.path.exists(test_outputs_path):
            raise FileNotFoundError(f"Test outputs file not found at: {test_outputs_path}")
            
        with open(test_outputs_path) as f:
            cls.test_outputs = json.load(f)
            
        # Load prompts from src/prompts_config
        try:
            with open(os.path.join(cls.prompts_path, 'creativity_prompt.yaml')) as f:
                cls.creativity_prompt = yaml.safe_load(f)
                
            with open(os.path.join(cls.prompts_path, 'story_circle_prompt.yaml')) as f:
                cls.story_circle_prompt = yaml.safe_load(f)
                
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Prompt files not found in {cls.prompts_path}. "
                f"Make sure creativity_prompt.yaml and story_circle_prompt.yaml exist in src/prompts_config"
            ) from e

        # Add printing logic here instead of setUp
        print("\n=== Test Data Overview ===")
        
        print("\n=== Creativity Prompt Output ===")
        print("1. Creative Storm Analysis:")
        cs_content = cls.extract_tag_content(
            cls.test_outputs['creativity_prompt_output']['output'], 
            'CS'
        )
        print(cs_content)
        
        print("\n2. Story Circle Instructions:")
        instructions = cls.extract_tag_content(
            cls.test_outputs['creativity_prompt_output']['output'], 
            'INSTRUCTIONS'
        )
        try:
            yaml_content = yaml.safe_load(instructions)
            print("\nFormatted YAML Content:")
            print(yaml.dump(yaml_content, sort_keys=False, allow_unicode=True))
        except yaml.YAMLError as e:
            print(f"Error parsing YAML: {e}")
        
        print("\n=== Story Circle Prompt Output ===")
        output = cls.test_outputs['story_circle_prompt_output']['output']
        for i in range(1, 5):
            print(f"\nStory Circle {i}:")
            circle_content = cls.extract_tag_content(output, f'story_circle_{i}')
            if circle_content:
                try:
                    circle_json = json.loads(circle_content)
                    print(json.dumps(circle_json, indent=2))
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON: {e}")

    @classmethod
    def extract_tag_content(cls, text: str, tag: str) -> Optional[str]:
        """Helper to extract content between XML tags"""
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    def test_creativity_prompt_output_structure(self):
        """Test if creativity prompt output follows required format"""
        output = self.test_outputs['creativity_prompt_output']['output']
        
        # Test CS tags presence
        cs_content = self.extract_tag_content(output, 'CS')
        self.assertIsNotNone(cs_content, "CS tags missing")
        
        # Test INSTRUCTIONS tags and content
        instructions = self.extract_tag_content(output, 'INSTRUCTIONS')
        self.assertIsNotNone(instructions, "INSTRUCTIONS tags missing")
        
        # Parse YAML content
        try:
            yaml_content = yaml.safe_load(instructions)
            self.assertIn('story_circles', yaml_content)
            self.assertEqual(len(yaml_content['story_circles']), 4)
        except yaml.YAMLError as e:
            self.fail(f"Invalid YAML in instructions: {e}")

    def test_story_circle_prompt_output_structure(self):
        """Test if story circle prompt output follows required format"""
        output = self.test_outputs['story_circle_prompt_output']['output']
        
        # Test presence of all four story circle tags
        for i in range(1, 5):
            circle_content = self.extract_tag_content(output, f'story_circle_{i}')
            self.assertIsNotNone(circle_content, f"story_circle_{i} tags missing")
            
            # Validate JSON structure
            try:
                circle_json = json.loads(circle_content)
                self.validate_story_circle_structure(circle_json)
            except json.JSONDecodeError as e:
                self.fail(f"Invalid JSON in story_circle_{i}: {e}")

    def validate_story_circle_structure(self, circle: Dict):
        """Helper to validate story circle structure"""
        self.assertIn('narrative', circle)
        self.assertIn('current_story_circle', circle['narrative'])
        
        phases = circle['narrative']['current_story_circle']
        self.assertTrue(isinstance(phases, list))
        
        for phase in phases:
            self.assertIn('phase', phase)
            self.assertIn('description', phase)
            self.assertIn('events', phase)
            self.assertIn('inner_dialogues', phase)
            
            # Validate events and dialogues are lists with 1-2 items
            self.assertTrue(isinstance(phase['events'], list))
            self.assertTrue(0 < len(phase['events']) <= 2)
            self.assertTrue(isinstance(phase['inner_dialogues'], list))
            self.assertTrue(0 < len(phase['inner_dialogues']) <= 2)

if __name__ == '__main__':
    unittest.main(verbosity=2) 