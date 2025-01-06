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
                prompts = yaml.safe_load(f)
                
            # Validate required prompts exist
            if not prompts or 'marketcap' not in prompts:
                logger.error("Missing required prompts in announcement_prompts.yaml")
                return {}
                
            if 'content_prompt' not in prompts['marketcap']:
                logger.error("Missing content_prompt in marketcap prompts")
                return {}
                
            logger.info("Successfully loaded announcement prompts")
            return prompts
        except Exception as e:
            logger.error(f"Error loading announcement prompts: {e}")
            return {}

    def generate_marketcap_announcement(self, base_announcement: str, current_event: str, inner_dialogue: str) -> str:
        """Generate narrative-aware marketcap announcement"""
        try:
            if not self.prompts:
                logger.error("No prompts available for announcement generation")
                return base_announcement

            # Validate inputs
            if not current_event or not inner_dialogue:
                logger.warning("Missing narrative context elements")
                return base_announcement

            prompt = self.prompts['marketcap']['content_prompt'].format(
                base_announcement=base_announcement,
                current_event=current_event,
                inner_dialogue=inner_dialogue
            )
            
            logger.debug(f"Generated prompt for LLM: {prompt}")

            messages = [
                {"role": "system", "content": "You are a street-smart AI agent providing market updates."},
                {"role": "user", "content": prompt}
            ]

            logger.info("Sending request to LLM...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            generated_content = response.choices[0].message.content.strip()
            logger.debug(f"Raw LLM response: {generated_content}")

            # Validate the generated content
            if not generated_content:
                logger.warning("LLM returned empty content, using base announcement")
                return base_announcement

            # Ensure we don't exceed Twitter limit
            if len(generated_content) > 280:
                generated_content = generated_content[:277] + "..."

            logger.info(f"Successfully generated narrative announcement: {generated_content}")
            return generated_content

        except Exception as e:
            logger.error(f"Error generating announcement: {str(e)}", exc_info=True)
            return base_announcement  # Fallback to original announcement