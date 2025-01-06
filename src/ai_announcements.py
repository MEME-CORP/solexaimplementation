from openai import OpenAI
import yaml
from pathlib import Path
import logging
from src.config import Config
from src.database.supabase_client import DatabaseService

logger = logging.getLogger('ai_announcements')

class AIAnnouncements:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.model = Config.AI_MODEL2
        self.temperature = 0.7
        self.max_tokens = 70
        self.prompts = self._load_prompts()
        self.db = DatabaseService()

    def _load_prompts(self):
        """Load announcement prompts from YAML"""
        try:
            prompts_path = Path(__file__).parent / 'prompts_config' / 'announcement_prompts.yaml'
            with open(prompts_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading announcement prompts: {e}")
            return {}

    def _get_narrative_context(self):
        """Get current narrative context from database"""
        try:
            story_circle = self.db.get_story_circle_sync()
            if not story_circle:
                logger.warning("No story circle found in database")
                return '', ''
            
            current_event = story_circle['dynamic_context'].get('current_event', '')
            inner_dialogue = story_circle['dynamic_context'].get('current_inner_dialogue', '')
            
            return current_event, inner_dialogue
            
        except Exception as e:
            logger.error(f"Error getting narrative context: {e}")
            return '', ''

    def generate_marketcap_announcement(self, base_announcement: str, current_event: str = '', inner_dialogue: str = '') -> str:
        """Generate narrative-aware marketcap announcement"""
        try:
            # Check prompts first
            if not self.prompts:
                logger.error("No prompts available for announcement generation")
                return base_announcement

            # If no context provided, get it from database
            if not current_event or not inner_dialogue:
                current_event, inner_dialogue = self._get_narrative_context()
                logger.info(f"Using database context - Event: {current_event}, Dialogue: {inner_dialogue}")

            prompt = self.prompts['marketcap']['content_prompt'].format(
                base_announcement=base_announcement,
                current_event=current_event,
                inner_dialogue=inner_dialogue
            )

            messages = [
                {"role": "system", "content": "You are a street-smart AI agent providing market updates."},
                {"role": "user", "content": prompt}
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            generated_content = response.choices[0].message.content

            # Ensure we don't exceed Twitter limit
            if len(generated_content) > 280:
                generated_content = generated_content[:277] + "..."

            return generated_content

        except Exception as e:
            logger.error(f"Error generating announcement: {e}")
            return base_announcement  # Fallback to original announcement 