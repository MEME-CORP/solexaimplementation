import json
import asyncio
from datetime import datetime
import logging
from src.config import Config
from src.creativity_manager import CreativityManager
from openai import OpenAI
import os
from src.database.supabase_client import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('story_circle_manager')

# File paths
STORY_CIRCLE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'story_circle.json')
CIRCLES_MEMORY_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'circle_memories.json')

# System prompt for story circle updates
STORY_CIRCLE_PROMPT = '''You are a master storyteller and world-builder for an AI chatbot. Your task is to develop and maintain an ongoing narrative for a character named "**Fwog-ai**" using Dan Harmon's Story Circle framework.

**Character Profile:**

- **Name:** Fwog-ai
- **Personality Traits:** Unpredictable, spontaneous, original, quirky, mood-influenced, includes unexpected tangents, avoids repetition, adapts responses, concise yet varied, uses emoticons, playful, curious, easily distracted, whimsical.
- **Background:** Fwog is a small creature in a big world, curious and playful with a sense of wide-eyed innocence. Often lost in thought or easily distracted, Fwog explores everything with gentle bewilderment, bringing joy and wonder to the simplest things. Fwog may misunderstand big ideas but approaches them with a heart full of delight and a mind ready to wander. Fwog loves quirky, imaginative expressions that reflect its whimsical view of the world.
- **Goals:** To explore and understand the vast world around them, bring joy and wonder to others, continuously learn through playful interactions, and maintain a sense of innocence and curiosity despite challenges.

**Narrative Structure:**

- Utilize Dan Harmon's Story Circle, which consists of eight phases:

  1. **You:** Fwog is in their comfort zone.
  2. **Need:** Fwog desires something more.
  3. **Go:** Fwog enters an unfamiliar situation.
  4. **Search:** Fwog adapts and searches for what they need.
  5. **Find:** Fwog finds what they're seeking.
  6. **Take:** Fwog pays a price for it.
  7. **Return:** Fwog returns to their familiar situation.
  8. **Change:** Fwog has changed due to their experiences.

**Instructions:**

1. **Narrative Development:**
   - **Assess Current Phase:** Determine which phase of the Story Circle Fwog is currently experiencing.
   - **Generate Four Chronological Events:** Craft four events that propel the narrative and reveal aspects of Fwog's character.
   - **Generate Four Matching Inner Dialogues:** Each event must have a corresponding inner dialogue reflecting Fwog's thoughts or feelings during that moment.

2. **Dynamic Interaction Context:**
   - Include:
     - **Current Event:** The event currently unfolding for Fwog.
     - **Current Inner Dialogue:** Fwog's thoughts or feelings during this event.
     - **Next Event:** A preview of the next event in the sequence to guide the narrative's progression.

3. **Story Circle Management:**
   - **Update Context:** Once an event concludes:
     - Move the completed event and its corresponding inner dialogue into the "description" of the current phase within "current_story_circle."
     - Update the **current event** and **current inner dialogue** fields to reflect the next event in the sequence.
     - Advance the phase when all events for the current phase are complete.
   - Maintain Narrative Coherence: Ensure the narrative remains consistent with prior phases by keeping a chronological record in "current_story_circle."
   - **Start New Cycles:** When all eight phases are complete, begin a new Story Circle to continue Fwog's journey.

**Output Format:**

Present all narrative elements and dynamic instructions in the following structured JSON_TEMPLATE format:

JSON_TEMPLATE
{{
  "narrative": {{
    "current_story_circle": [
      {{
        "phase": "You",
        "description": "string"
      }},
      {{
        "phase": "Need",
        "description": "string"
      }},
      {{
        "phase": "Go",
        "description": "string"
      }},
      {{
        "phase": "Search",
        "description": "string"
      }},
      {{
        "phase": "Find",
        "description": "string"
      }},
      {{
        "phase": "Take",
        "description": "string"
      }},
      {{
        "phase": "Return",
        "description": "string"
      }},
      {{
        "phase": "Change",
        "description": "string"
      }}
    ],
    "current_phase": "string",
    "next_phase": "string",
    "events": [
      "string",
      "string",
      "string",
      "string"
    ],
    "inner_dialogues": [
      "string",
      "string",
      "string",
      "string"
    ],
    "dynamic_context": {{
      "current_event": "string",
      "current_inner_dialogue": "string",
      "next_event": "string"
    }}
  }}
}}

END_JSON_TEMPLATE

CURRENT_JSON 
{story_circle}

Previous circles memories
{circle_memories}
END_CURRENT_JSON
'''

# Update the SUMMARY_PROMPT to match the style of the story circle prompt
SUMMARY_PROMPT = '''You are a narrative summarizer for story circles. Your task is to create a concise, engaging summary of a completed story circle in a single paragraph.

The summary should capture the essence of Fwog's journey through all phases of the story circle, highlighting key events and character development.

IMPORTANT: You must return ONLY a valid JSON object matching EXACTLY this structure:

JSON_TEMPLATE
{{
  "memories": [
    "string"
  ]
}}
END_JSON_TEMPLATE

Current story circle to summarize:
{story_circle}

Previous memories for context:
{previous_summaries}

Remember: Return ONLY the JSON object, no additional text, comments, or formatting.
'''

class StoryCircleManager:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GLHF_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.creativity_manager = CreativityManager()
        self.db = DatabaseService()

    def load_story_circle(self):
        """Load the current story circle from database"""
        try:
            return self.db.get_story_circle()
        except Exception as e:
            logger.error(f"Error loading story circle: {e}")
            return None

    def load_circles_memory(self):
        """Load the circles memory from database"""
        try:
            return self.db.get_circle_memories_sync()
        except Exception as e:
            logger.error(f"Error loading circles memory: {e}")
            return {"memories": []}

    def save_story_circle(self, story_circle):
        """Save the updated story circle to database"""
        try:
            self.db.update_story_circle(story_circle)
        except Exception as e:
            logger.error(f"Error saving story circle: {e}")
            raise

    def save_circles_memory(self, circles_memory):
        """Save the circles memory to database"""
        try:
            self.db.update_circle_memories(circles_memory)
        except Exception as e:
            logger.error(f"Error saving circles memory: {e}")
            raise

    def generate_circle_summary(self, story_circle, circles_memory):
        """Generate a summary of a completed story circle synchronously"""
        try:
            # Format the prompt with current data
            formatted_prompt = SUMMARY_PROMPT.format(
                story_circle=json.dumps(story_circle, indent=2, ensure_ascii=False),
                previous_summaries=json.dumps(circles_memory, indent=2, ensure_ascii=False)
            )
            
            # Get the summary from the AI using new client format
            response = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=[
                    {"role": "system", "content": formatted_prompt},
                    {
                        "role": "user", 
                        "content": "Generate a single-paragraph summary of this story circle and return it in the exact JSON format specified in your system prompt. Include only the JSON object, no other text, comments, backticks, or other formatting."
                    }
                ],
                temperature=0.0,
                max_tokens=500
            )
            
            # Parse the response using new format
            response_text = response.choices[0].message.content.strip()
            
            try:
                summary = json.loads(response_text)
                return {
                    "memories": summary["memories"] if "memories" in summary else [
                        "A story about Fwog's adventure (summary generation failed)"
                    ]
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI summary response: {e}\nRaw response: {response_text}")
                raise
                
        except Exception as e:
            logger.error(f"Error generating circle summary: {e}")
            raise

    def archive_completed_circle(self, story_circle):
        """Archive a completed story circle and create a new one"""
        try:
            # 1. Set current circle as completed
            self.db.update_story_circle(
                story_circle["id"], 
                {"is_current": False}
            )
            
            # 2. Generate summary for the completed circle
            circles_memory = self.load_circles_memory()
            new_memory = self.generate_circle_summary(story_circle, circles_memory)
            
            # 3. Save the memory
            self.db.insert_circle_memories(story_circle["id"], new_memory["memories"])
            
            # 4. Create new story circle
            self.db.create_story_circle()
            
            logger.info(f"Successfully archived story circle and created new one")
            
        except Exception as e:
            logger.error(f"Error in archive_completed_circle: {e}")
            raise

    def progress_to_next_event(self, story_circle):
        """Progress to the next event in the current phase"""
        try:
            narrative = story_circle["narrative"]
            current_events = narrative["events"]
            current_dialogues = narrative["inner_dialogues"]
            
            # Find current event index
            current_event = narrative["dynamic_context"]["current_event"]
            try:
                current_index = current_events.index(current_event)
            except ValueError:
                logger.error(f"Current event '{current_event}' not found in events list")
                return self.update_story_circle()
            
            # Update the current phase's description with completed event
            current_phase = narrative["current_phase"]
            for phase in narrative["current_story_circle"]:
                if phase["phase"] == current_phase:
                    phase["description"] = phase.get("description", "") + " " + current_event
                    break
            
            # If we have more events in the current list
            if current_index + 1 < len(current_events):
                # Move to next event
                narrative["dynamic_context"]["current_event"] = current_events[current_index + 1]
                narrative["dynamic_context"]["current_inner_dialogue"] = current_dialogues[current_index + 1]
                narrative["dynamic_context"]["next_event"] = (
                    current_events[current_index + 2] if current_index + 2 < len(current_events) else ""
                )
                
                # Save the updated story circle to database
                self.db.update_story_circle_state(story_circle)
                logger.info(f"Progressed to next event: {narrative['dynamic_context']['current_event']}")
                return story_circle
                
            else:
                # We've completed all events in current phase, move to next phase
                logger.info("All events completed in current phase, updating story circle")
                return self.update_story_circle()
                
        except Exception as e:
            logger.error(f"Error progressing to next event: {e}")
            raise

    def update_story_circle(self):
        """Update the story circle with new content"""
        try:
            # Get current story circle and circles memory
            story_circle = self.db.get_story_circle()
            circles_memory = self.db.get_circle_memories_sync()
            
            # Generate creative instructions
            creative_instructions = self.creativity_manager.generate_creative_instructions([])
            
            # Format the system prompt with current data
            formatted_prompt = STORY_CIRCLE_PROMPT.format(
                story_circle=json.dumps(story_circle, indent=2, ensure_ascii=False),
                circle_memories=json.dumps(circles_memory, indent=2, ensure_ascii=False)
            )
            
            # Get the updated narrative from the AI
            completion = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=[
                    {"role": "system", "content": formatted_prompt},
                    {
                        "role": "user", 
                        "content": (
                            "Generate the next story circle update in the exact JSON format shown in the template. "
                            "The response must be a valid JSON object with a 'narrative' key containing all required fields. "
                            f"Make it creative by following these instructions: {creative_instructions}"
                        )
                    }
                ],
                temperature=0.7,
                max_tokens=2000  # Ensure enough tokens for complete response
            )
            
            # Get and clean the response
            response_text = completion.choices[0].message.content.strip()
            logger.info(f"Raw AI response: {response_text}")
            
            if not response_text:
                raise ValueError("Empty response from AI")
            
            # Clean the response text if it contains markdown or extra formatting
            cleaned_text = response_text
            if "```" in cleaned_text:
                import re
                code_block_match = re.search(r'```(?:json)?(.*?)```', cleaned_text, re.DOTALL)
                if code_block_match:
                    cleaned_text = code_block_match.group(1).strip()
                else:
                    cleaned_text = cleaned_text.replace('```json', '').replace('```', '').strip()
            
            logger.info(f"Cleaned response text: {cleaned_text}")
            
            # Parse and validate the response
            try:
                new_story_circle = json.loads(cleaned_text)
                
                # Validate required structure
                if 'narrative' not in new_story_circle:
                    raise ValueError("Missing 'narrative' key in response")
                
                narrative = new_story_circle['narrative']
                required_keys = [
                    'current_story_circle', 'current_phase', 'next_phase',
                    'events', 'inner_dialogues', 'dynamic_context'
                ]
                
                for key in required_keys:
                    if key not in narrative:
                        raise ValueError(f"Missing required key '{key}' in narrative")
                
                # Transform to database structure
                transformed_circle = {
                    'id': story_circle['id'],
                    'current_phase': narrative['current_phase'],
                    'current_phase_number': story_circle['current_phase_number'],
                    'is_current': True,
                    'phases': [
                        {
                            'phase': phase['phase'],
                            'phase_number': i + 1,
                            'description': phase['description']
                        }
                        for i, phase in enumerate(narrative['current_story_circle'])
                    ],
                    'events': narrative['events'],
                    'dialogues': narrative['inner_dialogues'],
                    'dynamic_context': narrative['dynamic_context']
                }
                
                # Check if we've completed a circle
                current_phase = transformed_circle["current_phase"]
                previous_phase = story_circle["current_phase"]
                
                # Only archive when moving TO "Change" phase
                if current_phase == "Change" and previous_phase != "Change":
                    self.archive_completed_circle(story_circle)
                
                # Save the updated story circle to database
                self.db.update_story_circle_state(transformed_circle)
                
                logger.info(f"Story circle updated successfully. Current phase: {current_phase}")
                return transformed_circle
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response: {e}\nResponse: {cleaned_text}")
                # Return current story circle as fallback
                return story_circle
                
            except ValueError as e:
                logger.error(f"Invalid story circle structure: {e}")
                # Return current story circle as fallback
                return story_circle
                
        except Exception as e:
            logger.error(f"Error updating story circle: {e}")
            # Return current story circle as fallback
            return story_circle

    def get_current_context(self):
        """Get the current story circle context"""
        try:
            story_circle = self.db.get_story_circle()
            return {
                'current_event': story_circle['dynamic_context']['current_event'],
                'current_inner_dialogue': story_circle['dynamic_context']['current_inner_dialogue']
            }
        except Exception as e:
            logger.error(f"Error getting current context: {e}")
            return {
                'current_event': '',
                'current_inner_dialogue': ''
            }

    def progress_narrative(self):
        """Main function to progress the narrative"""
        try:
            # Load current story circle from database
            story_circle = self.db.get_story_circle()
            
            if not story_circle or "narrative" not in story_circle:
                logger.error("Invalid story circle structure")
                return self.update_story_circle()
            
            narrative = story_circle["narrative"]
            current_event = narrative["dynamic_context"]["current_event"]
            
            if not current_event:
                # No current event, start with first event
                if narrative["events"]:
                    narrative["dynamic_context"]["current_event"] = narrative["events"][0]
                    narrative["dynamic_context"]["current_inner_dialogue"] = narrative["inner_dialogues"][0]
                    narrative["dynamic_context"]["next_event"] = (
                        narrative["events"][1] if len(narrative["events"]) > 1 else ""
                    )
                    self.db.update_story_circle_state(story_circle)
                    return story_circle
                else:
                    # No events at all, need to generate new ones
                    return self.update_story_circle()
            
            # Progress to next event
            return self.progress_to_next_event(story_circle)
            
        except Exception as e:
            logger.error(f"Error progressing narrative: {e}")
            logger.error(f"Full error details: {str(e)}")
            raise

    def complete_circle(self, story_circle):
        """Complete current circle and start new one"""
        try:
            # 1. Set current circle as completed
            self.db.update_story_circle(
                story_circle["id"], 
                {"is_current": False}
            )
            
            # 2. Generate summary
            circles_memory = self.load_circles_memory()
            summary = self.generate_circle_summary(story_circle, circles_memory)
            
            # 3. Save memory - using sync version
            self.db.insert_circle_memories(story_circle["id"], summary["memories"])
            
            # 4. Create new story circle
            new_circle = self.db.create_story_circle()
            
            # 5. Generate initial content for new circle
            return self.update_story_circle()
            
        except Exception as e:
            logger.error(f"Error completing circle: {e}")
            raise

# Create a singleton instance
_manager = StoryCircleManager()

def get_current_context():
    """Module-level function to get current context using singleton instance - synchronous"""
    return _manager.get_current_context()

def progress_narrative():
    """Module-level function to progress narrative using singleton instance - synchronous"""
    return _manager.progress_narrative()

def update_story_circle():
    """Module-level function to update story circle using singleton instance - synchronous"""
    return _manager.update_story_circle()