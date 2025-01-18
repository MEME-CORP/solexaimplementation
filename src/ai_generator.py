# src/ai_generator.py

from openai import OpenAI
import random
import json
from src.config import Config
import logging
import os
import re
import os.path
import traceback
from src.database.supabase_client import DatabaseService
import yaml
from pathlib import Path
from src.memory_decision import MemoryDecision

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ai_generator')

class AIGenerator:
    def __init__(self, mode='twitter'):
        self.mode = mode
        
        # Initialize these first
        logger.info("Initializing AIGenerator")
        self.db = DatabaseService()
        self.memories = None
        
        # Load narrative data first
        logger.info("Loading narrative data")
        story_circle = self.db.get_story_circle_sync()
        if story_circle:
            logger.info(f"Successfully loaded story circle with {len(story_circle.get('events', []))} events")
            self.narrative = story_circle
        else:
            logger.warning("No story circle found, initializing empty narrative")
            self.narrative = {
                'events': [],
                'dialogues': [],
                'dynamic_context': {}
            }
        
        # Mode-specific settings
        if mode == 'twitter':
            self.max_tokens = 70
            self.temperature = 0.0
            self.length_formats = self.load_length_formats()
            self.emotion_formats = self.load_emotion_formats()
        elif mode == 'discord':
            self.max_tokens = 40
            self.temperature = 0.9
            self.emotion_formats = self.load_emotion_formats()
        else:  # telegram or other
            self.max_tokens = 70
            self.temperature = 0.4
            self.emotion_formats = self.load_emotion_formats()
            
        # Load appropriate system prompt based on mode
        self.system_prompt = self._load_system_prompt()
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        
        # Always use Gemma for direct user interactions
        self.model = Config.AI_MODEL2  # This is gemma-2-9b-it

        # Initialize memory decision
        self.memory_decision = MemoryDecision()
        
        # Load memories using memory_decision instead of direct db access
        logger.info("Loading memories and narrative")
        try:
            self.memories = self.memory_decision.get_memories_sync()
            logger.info(f"Successfully loaded {len(self.memories)} memories")
        except Exception as e:
            logger.error(f"Error loading memories: {e}")
            self.memories = []

        try:
            self.narrative = self.db.get_story_circle_sync()
            if self.narrative:
                logger.info("Successfully loaded narrative")
            else:
                logger.warning("No narrative loaded")
        except Exception as e:
            logger.error(f"Error loading narrative: {e}")
            self.narrative = None

        # Load bot prompts
        self.bot_prompts = self._load_bot_prompts()
        
        logger.info(f"Initialization complete. Memories loaded: {bool(self.memories)}, Narrative loaded: {bool(self.narrative)}")

    def load_length_formats(self):
        """Load length formats from JSON file"""
        try:
            # Get the path to the length_formats.json file
            file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'length_formats.json')
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                formats = data.get('formats', [])
                if not formats:
                    logger.warning("No length formats found in file")
                    return [{"format": "one short sentence", "description": "Single concise sentence"}]
                return formats
                
        except Exception as e:
            logger.error(f"Error loading length formats from file: {e}")
            return [{"format": "one short sentence", "description": "Single concise sentence"}]

    def load_emotion_formats(self):
        """Load emotion formats from JSON file"""
        try:
            # Get the path to the emotion_formats.json file
            file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'emotion_formats.json')
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                formats = data.get('formats', [])
                if not formats:
                    logger.warning("No emotion formats found in file")
                    return [{"format": "default response", "description": "Standard emotional response"}]
                return formats
                
        except Exception as e:
            logger.error(f"Error loading emotion formats from file: {e}")
            return [{"format": "default response", "description": "Standard emotional response"}]

    def load_memories(self):
        """Load memories from database through memory decision"""
        try:
            memories = self.memory_decision.get_all_memories()
            logger.info(f"Successfully loaded {len(memories)} memories")
            return memories
        except Exception as e:
            logger.error(f"Error loading memories: {str(e)}")
            return []

    def load_narrative(self):
        """Load narrative context"""
        try:
            story_circle = self.db.get_story_circle_sync()
            if story_circle:
                logger.info("Narrative content:")
                logger.info(f"Current Phase: {story_circle.get('current_phase')}")
                logger.info(f"Events count: {len(story_circle.get('events', []))}")
                logger.info(f"Dialogues count: {len(story_circle.get('dialogues', []))}")
                logger.info(f"Current Event: {story_circle.get('dynamic_context', {}).get('current_event')}")
                logger.info(f"Current Inner Dialogue: {story_circle.get('dynamic_context', {}).get('current_inner_dialogue')}")
                
                # Verify events and dialogues are present
                events = story_circle.get('events', [])
                dialogues = story_circle.get('dialogues', [])
                if events and dialogues:
                    logger.info("Sample of events and dialogues:")
                    for i, (event, dialogue) in enumerate(zip(events[:2], dialogues[:2])):
                        logger.info(f"Event {i+1}: {event}")
                        logger.info(f"Dialogue {i+1}: {dialogue}")
                
                return story_circle
            else:
                logger.warning("No story circle found in database")
                return None
        except Exception as e:
            logger.error(f"Error loading narrative: {e}")
            return None

    def _load_bot_prompts(self):
        """Load bot prompts from YAML file"""
        try:
            prompts_path = Path(__file__).parent / 'prompts_config' / 'bot_prompts.yaml'
            with open(prompts_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading bot prompts: {e}")
            return {}

    def _prepare_messages(self, **kwargs):
        """Prepare messages for API call - exposed for testing"""
        logger.info("Starting message preparation with mode: %s", self.mode)
        
        # Refresh narrative data to ensure we have latest events/dialogues
        story_circle = self.db.get_story_circle_sync()
        if story_circle:
            self.narrative = story_circle
            logger.info(f"Refreshed narrative data with {len(story_circle.get('events', []))} events")
        
        # Modified memory handling
        memories = kwargs.get('memories', self.memories)
        memory_context = (
            "no relevant memories for this conversation" 
            if not memories
            else memories if isinstance(memories, (str, list))
            else "no relevant memories for this conversation"
        )
        
        # Add logging for memory selection output
        logger.info("Selected memories for context:")
        logger.info("----------------------------------------")
        logger.info(memory_context)
        logger.info("----------------------------------------")
        
        # If memories is a list, format it properly
        if isinstance(memory_context, list):
            memory_context = "\n".join(f"- {memory}" for memory in memory_context)
        
        logger.debug("Memory context prepared: %s", memory_context[:100] + "..." if len(str(memory_context)) > 100 else memory_context)
        
        # Extract events and dialogues directly from narrative
        events = self.narrative.get('events', [])
        dialogues = self.narrative.get('dialogues', [])
        
        # Enhanced logging for events and dialogues
        logger.info("Current phase events and dialogues:")
        for i, (event, dialogue) in enumerate(zip(events, dialogues)):
            logger.info(f"Event {i+1}: {event}")
            logger.info(f"Dialogue {i+1}: {dialogue}")
        
        # Format events and dialogues for prompt
        phase_events = "\n".join(f"{i+1}. {event}" for i, event in enumerate(events)) if events else "No events yet"
        phase_dialogues = "\n".join(f"{i+1}. {dialogue}" for i, dialogue in enumerate(dialogues)) if dialogues else "No dialogues yet"
        
        logger.info(f"Formatted {len(events)} events and {len(dialogues)} dialogues")
        
        # Get dynamic context
        dynamic_context = self.narrative.get('dynamic_context', {})
        current_event = dynamic_context.get('current_event', '')
        inner_dialogue = dynamic_context.get('current_inner_dialogue', '')
        
        # Get the appropriate prompt template based on mode
        if self.mode == 'twitter':
            prompt_template = self.bot_prompts.get('twitter', {}).get('content_prompt', '')
            
            # Randomly choose between current instructions and memories
            use_memories = random.random() < 0.1  # 20% chance to use memories
            logger.info("Content generation mode: %s", "Using memories" if use_memories else "Using current instructions")
            
            if use_memories:
                # When using memories, we should clear or minimize narrative context
                phase_events = "No events to consider"
                phase_dialogues = "No dialogues to consider"
                current_event = ""
                inner_dialogue = ""
                # Ensure we're using the memory context
                if self.memories:
                    memory_context = random.choice(self.memories) if isinstance(self.memories, list) else self.memories
                    logger.info(f"Selected memory for generation: {memory_context}")
                else:
                    logger.warning("No memories available for selection")
                    memory_context = "no memories available"
            
            tweet_content = (
                f"user_message: {kwargs.get('user_message', '')[9:].strip()} - based on one topic from your events and dialogues" if kwargs.get('user_message', '').startswith('reply to:')
                else "one of your memories randomly" if use_memories
                else "one topic from your events and dialogues"
            )
            
            # If using memories, refresh them from database
            if use_memories:
                logger.info("Fetching fresh memories from database")
                self.memories = self.db.get_memories()
                if self.memories:
                    logger.info("Successfully retrieved %d memories", len(self.memories))
                else:
                    logger.warning("No memories found in database")
            
            emotion_format = random.choice(self.emotion_formats)['format']
            length_format = random.choice(self.length_formats)['format']
            
            logger.info("Preparing Twitter prompt with variables:")
            logger.info("- Tweet content: %s", tweet_content)
            logger.info("- Emotion format: %s", emotion_format)
            logger.info("- Length format: %s", length_format)
            
            content_prompt = prompt_template.format(
                tweet_content=tweet_content,
                length_format=length_format,
                emotion_format=emotion_format,
                memory_context=memory_context,
                conversation_context=kwargs.get('conversation_context', ''),
                phase_events=phase_events,
                phase_dialogues=phase_dialogues,
                current_event=current_event,
                inner_dialogue=inner_dialogue
            )
            
            # Enhanced logging for prompt variables
            logger.info("Formatted prompt variables:")
            logger.info("Phase Events:\n%s", phase_events)
            logger.info("Phase Dialogues:\n%s", phase_dialogues)
            logger.info("Current Event: %s", current_event)
            logger.info("Inner Dialogue: %s", inner_dialogue)
            
            logger.debug("Generated content prompt: %s", content_prompt[:200] + "..." if len(content_prompt) > 200 else content_prompt)
        else:
            # Discord and Telegram format
            prompt_template = self.bot_prompts.get('discord_telegram', {}).get('content_prompt', '')
            emotion_format = random.choice(self.emotion_formats)['format']
            
            content_prompt = prompt_template.format(
                conversation_context=kwargs.get('conversation_context', ''),
                username=kwargs.get('username') or kwargs.get('user_id'),
                user_message=kwargs.get('user_message', ''),
                emotion_format=emotion_format,
                memory_context=memory_context,
                phase_events=phase_events,
                phase_dialogues=phase_dialogues,
                current_event=current_event,
                inner_dialogue=inner_dialogue
            )

        # Format the system prompt with context variables
        if self.mode == 'twitter':
            formatted_system_prompt = self.system_prompt.format(
                emotion_format=emotion_format,
                length_format=length_format,
                memory_context=memory_context,
                phase_events=phase_events,
                phase_dialogues=phase_dialogues
            )
        else:  # discord and telegram only need memory_context
            formatted_system_prompt = self.system_prompt.format(
                memory_context=memory_context
            )

        messages = [
            {
                "role": "system",
                "content": formatted_system_prompt
            },
            {
                "role": "user",
                "content": content_prompt
            }
        ]

        return messages

    def generate_content(self, **kwargs):
        """Generate content synchronously"""
        try:
            logger.info("Starting content generation with mode: %s", self.mode)
            
            # Get relevant memories for all modes
            user_id = kwargs.get('user_id', '')
            user_message = kwargs.get('user_message', '')
            
            try:
                # Select relevant memories based on user message for all modes
                memories = self.memory_decision.select_relevant_memories(
                    user_id or 'system',
                    user_message or 'generate content'
                )
                if memories and memories != "no relevant memories for this conversation":
                    kwargs['memories'] = memories
                    logger.info(f"Retrieved relevant memories for user {user_id or 'system'}")
                else:
                    # If no relevant memories, use a single random memory for variety
                    all_memories = self.memories or []
                    kwargs['memories'] = random.choice(all_memories) if all_memories else "no memories available"
                    logger.info("Using random memory due to no relevant matches")
            except Exception as e:
                logger.error(f"Error selecting memories: {e}")
                kwargs['memories'] = "no memories available"
            
            # Special handling for Twitter mode without user message
            if self.mode == 'twitter' and not user_message:
                narrative_context = kwargs.get('narrative_context', {})
                current_event = narrative_context.get('current_event', '')
                if current_event:
                    logger.info("Using current event context for random tweet: %s", current_event)
                    kwargs['memories'] = f"Current event context: {current_event}"
            
            messages = self._prepare_messages(**kwargs)
            
            # Add detailed logging of the complete system prompt
            if self.mode == 'twitter':
                logger.info("Complete Twitter system prompt:")
                logger.info("----------------------------------------")
                for msg in messages:
                    logger.info(f"Role: {msg['role']}")
                    logger.info(f"Content:\n{msg['content']}")
                logger.info("----------------------------------------")
            
            logger.info("Generating content with configuration:")
            logger.info("- Model: %s", self.model)
            logger.info("- Temperature: %s", self.temperature)
            logger.info("- Max tokens: %s", self.max_tokens)
            
            # Log the messages being sent to the LLM
            logger.info("Messages being sent to LLM:")
            for msg in messages:
                logger.info("Role: %s", msg["role"])
                logger.info("Content preview: %s", msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"])
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            generated_content = response.choices[0].message.content
            
            # Log LLM response details
            logger.info("LLM Response Details:")
            logger.info("- Response length: %d characters", len(generated_content))
            logger.info("- First 100 chars: %s", generated_content[:100])
            logger.info("- Usage tokens: %s", getattr(response, 'usage', {}))
            
            # Validate response
            if not generated_content or not isinstance(generated_content, str):
                logger.error("Invalid response generated")
                raise ValueError("Generated content is invalid")
            
            if self.mode == 'twitter' and len(generated_content) > 280:
                logger.warning("Generated content exceeds Twitter limit, truncating from %d characters", len(generated_content))
                generated_content = generated_content[:277] + "..."
            
            logger.info("Successfully generated content:")
            logger.info("- Content length: %d characters", len(generated_content))
            logger.info("- Generated content: %s", generated_content)
            
            return generated_content

        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            logger.error(f"Context: memories={self.memories}, narrative={self.narrative}")
            raise

    def _load_system_prompt(self):
        """Load system prompt based on mode"""
        try:
            if self.mode == 'twitter':
                prompt_file = 'system_prompt.yaml'
            else:  # discord and telegram
                prompt_file = 'system_prompt_swarm_1.yaml'
            
            prompt_path = Path(__file__).parent / 'prompts_config' / prompt_file
            with open(prompt_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if 'system_prompt' in config:
                    logger.info(f"Successfully loaded system prompt for {self.mode} mode")
                    return config['system_prompt']
                logger.error(f"No system_prompt found in {prompt_file}")
                return ""
        except Exception as e:
            logger.error(f"Error loading system prompt for {self.mode} mode: {e}")
            return ""

    def get_memories_sync(self):
        """Get memories synchronously for response generation"""
        try:
            if not self.memories:  # If memories aren't loaded or are empty
                self.memories = self.db.get_memories_sync()
                logger.info(f"Retrieved {len(self.memories)} memories from database")
            return self.memories
        except Exception as e:
            logger.error(f"Error getting memories synchronously: {e}")
            return []

