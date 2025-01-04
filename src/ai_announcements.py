from openai import OpenAI
import yaml
from pathlib import Path
import logging
from src.config import Config

logger = logging.getLogger('ai_announcements')

class AIAnnouncements:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.model = Config.AI_MODEL2  # Using same model as AIGenerator
        self.temperature = 0.7
        self.max_tokens = 70
        self.prompts = self._load_prompts()

    def _load_prompts(self):
        """Load announcement prompts from YAML"""
        try:
            prompts_path = Path(__file__).parent / 'prompts_config' / 'announcement_prompts.yaml'
            with open(prompts_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading announcement prompts: {e}")
            return {}

    def generate_marketcap_announcement(self, base_announcement: str, current_event: str, inner_dialogue: str) -> str:
        """Generate narrative-aware marketcap announcement"""
        try:
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