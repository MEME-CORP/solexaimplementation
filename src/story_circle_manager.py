import json
import logging
from datetime import datetime
from src.config import Config
from src.creativity_manager import CreativityManager
from openai import OpenAI
import os
import yaml
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('story_circle_manager')

# File paths
STORY_CIRCLES_CSV = os.path.join(os.path.dirname(__file__), '..', 'data', 'story_circles.csv')

def load_yaml_prompt(filename):
    """Load a prompt from a YAML file"""
    try:
        # Get absolute path to the prompts_config directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(current_dir, 'prompts_config', filename)
        
        logger.info(f"Attempting to load prompt from: {prompt_path}")
        
        if not os.path.exists(prompt_path):
            logger.error(f"Prompt file not found: {prompt_path}")
            # Try alternative path resolution
            project_root = os.path.dirname(current_dir)
            alt_path = os.path.join(project_root, 'src', 'prompts_config', filename)
            
            if os.path.exists(alt_path):
                prompt_path = alt_path
                logger.info(f"Found prompt file at alternative path: {alt_path}")
            else:
                logger.error(f"Prompt file not found at alternative path: {alt_path}")
                return None
            
        with open(prompt_path, 'r', encoding='utf-8') as f:
            try:
                prompt_config = yaml.safe_load(f)
                logger.info(f"Loaded YAML content from {filename}: {type(prompt_config)}")
                
                if not prompt_config:
                    logger.error(f"Empty prompt configuration in {filename}")
                    return None
                
                # Check for either system_prompt or specific prompt keys
                prompt_text = None
                if 'system_prompt' in prompt_config:
                    prompt_text = prompt_config['system_prompt']
                    logger.info(f"Found system_prompt in {filename}")
                elif 'story_circle_prompt' in prompt_config and filename == 'story_circle_prompt.yaml':
                    prompt_text = prompt_config['story_circle_prompt']
                    logger.info(f"Found story_circle_prompt in {filename}")
                elif 'summary_prompt' in prompt_config and filename == 'summary_prompt.yaml':
                    prompt_text = prompt_config['summary_prompt']
                    logger.info(f"Found summary_prompt in {filename}")
                
                if not prompt_text:
                    logger.error(f"No valid prompt found in {filename}. Available keys: {list(prompt_config.keys())}")
                    return None
                
                logger.info(f"Successfully loaded prompt from {filename} (length: {len(str(prompt_text))})")
                return prompt_text
                
            except yaml.YAMLError as yaml_err:
                logger.error(f"YAML parsing error in {filename}: {str(yaml_err)}")
                return None
            
    except Exception as e:
        logger.error(f"Error loading prompt from {filename}: {str(e)}")
        logger.error(f"Current working directory: {os.getcwd()}")
        logger.error(f"File path attempted: {prompt_path}")
        return None

class StoryCircleManager:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.creativity_manager = CreativityManager()
        
        # Initialize CSV if it doesn't exist
        if not os.path.exists(STORY_CIRCLES_CSV):
            df = pd.DataFrame(columns=['id', 'datetime', 'story_circle', 'status', 'current_phase', 'next_phase'])
            df.to_csv(STORY_CIRCLES_CSV, index=False)

    def get_last_inactive_story_circle(self):
        """Get the last inactive story circle from CSV"""
        try:
            df = pd.read_csv(STORY_CIRCLES_CSV)
            inactive_circles = df[df['status'] == 'inactive']
            if not inactive_circles.empty:
                last_inactive = inactive_circles.iloc[-1]
                return json.loads(last_inactive['story_circle'])
            return None
        except Exception as e:
            logger.error(f"Error getting last inactive story circle: {e}")
            return None

    def save_story_circle(self, story_circle, status='active', current_phase='You', next_phase='Need'):
        """Save story circle to CSV with timestamp, status and phases"""
        try:
            df = pd.read_csv(STORY_CIRCLES_CSV)
            new_id = 1 if df.empty else df['id'].max() + 1
            
            # Clean up the story circle to remove any extra fields
            clean_circle = {
                "narrative": {
                    "current_story_circle": story_circle["narrative"]["current_story_circle"]
                }
            }
            
            new_row = {
                'id': new_id,
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'story_circle': json.dumps(clean_circle, separators=(',', ':')),  # Compact JSON
                'status': status,
                'current_phase': current_phase,
                'next_phase': next_phase
            }
            
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(STORY_CIRCLES_CSV, index=False)
            return new_id
        except Exception as e:
            logger.error(f"Error saving story circle: {e}")
            return None

    def update_story_circle(self, creative_instructions=None):
        """Generate or update story circle based on creative instructions"""
        try:
            # Get the last inactive story circle for context
            previous_circle = self.get_last_inactive_story_circle()
            
            # Load story circle prompt template
            with open(os.path.join('src', 'prompts_config', 'story_circle_prompt.yaml')) as f:
                prompt_template = yaml.safe_load(f)['story_circle_prompt']
            
            # Replace previous circle placeholder
            base_prompt = prompt_template.replace(
                "{{previous_circle}}", 
                json.dumps(previous_circle) if previous_circle else "None"
            )
            
            # Add creative instructions if provided
            full_prompt = f"{base_prompt}\n\nCreative Instructions:\n{creative_instructions}" if creative_instructions else base_prompt
            
            # Get new story circle from AI
            completion = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=[
                    {"role": "system", "content": full_prompt},
                    {
                        "role": "user", 
                        "content": (
                            "Generate a complete story circle, formatted as a JSON object. "
                            "The story circle should contain one to two highly detailed events and inner dialogues for each phase. "
                            "Focus on making each event rich in detail, compelling, and plausible. "
                            "Return ONLY valid JSON objects, exactly matching the template structure. "                            
                            "Do not include any additional text, markdown formatting, or explanations outside the JSON format."
                        )
                    }
                ],
                temperature=0.0,
                max_tokens=2000
            )
            
            response_text = completion.choices[0].message.content.strip()
            
            # Clean the response if it contains markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            story_circle = json.loads(response_text)
            
            # Ensure we only have the expected structure
            if "narrative" in story_circle and "current_story_circle" in story_circle["narrative"]:
                # Clean up any extra fields
                clean_circle = {
                    "narrative": {
                        "current_story_circle": story_circle["narrative"]["current_story_circle"]
                    }
                }
                
                # Save to CSV with initial phases
                self.save_story_circle(clean_circle, 'active', 'You', 'Need')
                
                return clean_circle
            else:
                raise ValueError("Invalid story circle structure received from AI")
            
        except Exception as e:
            logger.error(f"Failed to generate/update story circle: {e}")
            if 'response_text' in locals():
                logger.error(f"Raw response: {response_text}")
            raise

    def advance_phase(self, story_circle_id):
        """Advance to the next phase in the story circle"""
        try:
            df = pd.read_csv(STORY_CIRCLES_CSV)
            story_circle_row = df[df['id'] == story_circle_id].iloc[0]
            
            phases = ['You', 'Need', 'Go', 'Search', 'Find', 'Take', 'Return', 'Change']
            current_idx = phases.index(story_circle_row['current_phase'])
            next_idx = (current_idx + 1) % len(phases)
            
            # If we've completed a circle
            if next_idx == 0:  # Moving back to 'You'
                # Mark current circle as inactive
                df.loc[df['id'] == story_circle_id, 'status'] = 'inactive'
                df.to_csv(STORY_CIRCLES_CSV, index=False)
                
                # Generate new circle
                try:
                    creative_instructions = self.creativity_manager.generate_creative_instructions([])
                    new_circle = self.update_story_circle(creative_instructions)
                    return new_circle
                except Exception as e:
                    logger.error(f"Error creating new story circle: {e}")
                    return None
            else:
                # Update phases
                df.loc[df['id'] == story_circle_id, 'current_phase'] = phases[next_idx]
                df.loc[df['id'] == story_circle_id, 'next_phase'] = phases[(next_idx + 1) % len(phases)]
                df.to_csv(STORY_CIRCLES_CSV, index=False)
                
                return json.loads(story_circle_row['story_circle'])
            
        except Exception as e:
            logger.error(f"Failed to advance phase: {e}")
            raise

# Create a singleton instance
_manager = StoryCircleManager()

def update_story_circle():
    """Module-level function to update story circle using singleton instance"""
    return _manager.update_story_circle()
