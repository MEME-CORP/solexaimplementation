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
SUMMARY_PROMPT = '''You are a narrative summarizer tasked with summarizing the journey of Fwog-ai through a story circle. Your task is to create a concise, engaging summary of a completed story circle in a single paragraph.

Previous circle summaries for context:
{previous_summaries}

Current story circle to summarize:
{story_circle}

Return your summary in this exact JSON format:
{{
    "memories": [
        "A concise one-line summary of the entire story circle",
        "A key memorable moment from the journey",
        "An insight about Fwog's character development"
    ]
}}
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
        """Load existing circle memories"""
        try:
            return self.db.get_circle_memories()
        except Exception as e:
            logger.error(f"Error loading circles memory: {e}")
            return []

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
            
            # Parse the response with better error handling
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"Raw AI Response:\n{response_text}")
            
            try:
                summary = json.loads(response_text)
                if "memories" not in summary:
                    logger.error("Missing 'memories' key in summary")
                    return {
                        "memories": ["A story about Fwog's adventure (summary missing memories)"]
                    }
                return summary
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI summary response: {e}\nRaw response: {response_text}")
                return {
                    "memories": ["A story about Fwog's adventure (summary parsing failed)"]
                }
                
        except Exception as e:
            logger.error(f"Error generating circle summary: {e}")
            logger.exception("Full traceback:")
            return {
                "memories": ["A story about Fwog's adventure (summary generation failed)"]
            }

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
        """Progress to next event in the current phase"""
        try:
            # Get current phase data
            current_phase = story_circle["current_phase"]
            current_phase_number = story_circle["current_phase_number"]
            
            # Get current event and events list
            events = story_circle.get('events', [])
            current_event = story_circle['dynamic_context']['current_event']
            
            logger.info(f"Current phase: {current_phase}, Current event: {current_event}")
            
            # If no events exist, generate new ones
            if not events:
                logger.info("No events found, generating new ones")
                updated_circle = self.update_story_circle()
                if not updated_circle or not updated_circle.get('events'):
                    logger.error("Failed to generate new events")
                    return story_circle
                return updated_circle
            
            # Find current event index
            current_index = events.index(current_event) if current_event in events else -1
            
            # Check if we need to generate new events
            if current_index == len(events) - 1:
                logger.info("Completed all events in phase, updating phase description")
                
                # Update phase description with all events
                try:
                    for event in events:
                        self._update_phase_description(story_circle, event)
                    logger.info("Updated phase description with all events")
                    
                    # Complete current phase and progress to next
                    return self._complete_phase_and_progress(story_circle)
                except Exception as e:
                    logger.error(f"Error updating phase description: {e}")
                    return story_circle
            
            if current_index == -1:
                logger.info("No current event found, generating new ones")
                updated_circle = self.update_story_circle()
                if not updated_circle or not updated_circle.get('events'):
                    logger.error("Failed to generate new events")
                    return story_circle
                return updated_circle
            
            # Progress to next event
            next_event = events[current_index + 1]
            next_dialogue = story_circle['dialogues'][current_index + 1]
            
            # Update dynamic context
            story_circle['dynamic_context'].update({
                'current_event': next_event,
                'current_inner_dialogue': next_dialogue,
                'next_event': events[current_index + 2] if current_index + 2 < len(events) else ""
            })
            
            # Update phase description with current event
            try:
                self._update_phase_description(story_circle, current_event)
            except Exception as e:
                logger.error(f"Error updating phase description: {e}")
            
            # Update database state
            self.db.update_story_circle_state(story_circle)
            logger.info(f"Progressed to next event: {next_event}")
            return story_circle
                
        except Exception as e:
            logger.error(f"Error progressing to next event: {str(e)}")
            logger.exception("Full traceback:")
            return story_circle

    def _update_phase_description(self, story_circle, event):
        """Helper method to update phase description"""
        try:
            # Get current phase index
            current_phase_index = story_circle['current_phase_number'] - 1
            
            # Get current description and append new event
            current_description = story_circle['phases'][current_phase_index]['description']
            updated_description = f"{current_description} {event}".strip()
            
            # Update in database
            success = self.db.update_phase_description(
                story_circle["id"],
                story_circle["current_phase"],
                updated_description
            )
            
            if success:
                # Also update in memory
                story_circle['phases'][current_phase_index]['description'] = updated_description
                logger.info(f"Updated phase description for {story_circle['current_phase']}")
                logger.debug(f"New description: {updated_description}")
            else:
                logger.error("Failed to update phase description in database")
                raise Exception("Phase description update failed")
            
        except Exception as e:
            logger.error(f"Error updating phase description: {e}")
            raise

    def _complete_phase_and_progress(self, story_circle):
        """Helper method to complete current phase and progress to next"""
        try:
            logger.info("All events completed in current phase, updating story circle")
            
            # Get current phase info
            current_phase_index = story_circle['current_phase_number'] - 1
            current_phase = story_circle['phases'][current_phase_index]
            events = story_circle.get('events', [])
            
            # Build complete phase description
            phase_description = " ".join(events).strip()
            logger.info(f"Final phase description: {phase_description}")
            
            # Update phase description in database
            success = self.db.update_phase_description(
                story_circle["id"],
                story_circle["current_phase"],
                phase_description
            )
            
            if not success:
                logger.error("Failed to update phase description")
                raise Exception("Phase description update failed")
            
            # Check if this is the last phase (Change)
            if story_circle["current_phase"] == "Change":
                logger.info("Story circle completed, archiving and starting new circle")
                return self.complete_circle(story_circle)
            
            # Not the last phase, move to next phase
            next_phase = self._get_next_phase(story_circle["current_phase"])
            next_phase_number = story_circle["current_phase_number"] + 1
            
            # Update phase statuses in database
            self.db.client.table('story_phases')\
                .update({'is_current': False})\
                .eq('story_circle_id', story_circle["id"])\
                .eq('phase_name', story_circle["current_phase"])\
                .execute()
                
            self.db.client.table('story_phases')\
                .update({'is_current': True})\
                .eq('story_circle_id', story_circle["id"])\
                .eq('phase_name', next_phase)\
                .execute()
            
            logger.info(f"Updated phase status in database: {story_circle['current_phase']} -> {next_phase}")
            
            # Update story circle object
            story_circle.update({
                "current_phase": next_phase,
                "current_phase_number": next_phase_number,
                "events": [],  # Clear events for next phase
                "dialogues": [],  # Clear dialogues for next phase
                "dynamic_context": {
                    "current_event": "",
                    "current_inner_dialogue": "",
                    "next_event": ""
                }
            })
            
            # Save the updated story circle
            self.db.update_story_circle_state(story_circle)
            logger.info(f"Progressed to next phase: {next_phase}")
            
            # Generate new events for the next phase
            return self.update_story_circle()
            
        except Exception as e:
            logger.error(f"Error completing phase and progressing: {e}")
            logger.exception("Full traceback:")
            raise

    def update_story_circle(self):
        """Update story circle with new events from AI"""
        try:
            # Get current story circle
            story_circle = self.db.get_story_circle()
            if not story_circle:
                logger.error("No story circle found")
                return None
            
            # Get circles memory for context
            circles_memory = self.db.get_circle_memories()
            
            # Generate creative instructions
            creative_instructions = self.creativity_manager.generate_creative_instructions([])
            
            # Format the system prompt
            formatted_prompt = STORY_CIRCLE_PROMPT.format(
                story_circle=json.dumps(story_circle, indent=2, ensure_ascii=False),
                circle_memories=json.dumps(circles_memory, indent=2, ensure_ascii=False)
            )
            
            # Get new events from AI with explicit JSON formatting instruction
            completion = self.client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=[
                    {"role": "system", "content": formatted_prompt},
                    {
                        "role": "user", 
                        "content": (
                            "Generate exactly four new events and four matching inner dialogues "
                            "for the next phase in the story circle. "
                            "Return ONLY a valid JSON object exactly matching the template structure. "
                            "Do not include any additional text, markdown formatting, or explanations. "
                            f"Make it creative by following these instructions: {creative_instructions}"
                        )
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse response with better error handling
            response_text = completion.choices[0].message.content.strip()
            logger.debug(f"Raw AI response: {response_text}")
            
            if not response_text:
                logger.error("Empty response from AI")
                return story_circle
            
            # Clean the response if it contains markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Try to parse the cleaned response
            try:
                new_story_circle = json.loads(response_text)
                
                # Validate response structure
                if 'narrative' not in new_story_circle:
                    logger.error("Missing narrative in response")
                    return story_circle
                    
                narrative = new_story_circle['narrative']
                required_fields = ['current_story_circle', 'current_phase', 'next_phase', 
                                 'events', 'inner_dialogues', 'dynamic_context']
                
                missing_fields = [f for f in required_fields if f not in narrative]
                if missing_fields:
                    logger.error(f"Missing required fields in narrative: {missing_fields}")
                    return story_circle
                
                # Validate events and dialogues
                if len(narrative['events']) != 4 or len(narrative['inner_dialogues']) != 4:
                    logger.error("Invalid number of events or dialogues")
                    return story_circle
                
                # Transform AI response to story circle format
                transformed = self._transform_ai_response(new_story_circle, story_circle)
                if not transformed:
                    logger.error("Failed to transform AI response")
                    return story_circle
                
                # Update database
                self.db.update_story_circle_state(transformed)
                logger.info("Successfully updated story circle with new events")
                
                return transformed
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response: {e}")
                logger.error(f"Response text: {response_text}")
                return story_circle
                
        except Exception as e:
            logger.error(f"Error updating story circle: {e}")
            logger.exception("Full traceback:")
            return story_circle

    async def get_current_narrative(self):
        """Get the current narrative state from database tables"""
        try:
            # Get current story circle
            story_circle = await self.db.get_story_circle()
            if not story_circle:
                raise ValueError("No active story circle found")

            # Get phases for this story circle
            phases = await self.db.get_story_phases(story_circle['id'])
            
            # Get events and dialogues for the current phase
            current_phase = next((p for p in phases if p['is_current']), None)
            if not current_phase:
                raise ValueError("No current phase found")
            
            events_dialogues = await self.db.get_events_dialogues(
                story_circle['id'], 
                current_phase['phase_number']
            )

            # Construct narrative structure
            narrative = {
                "current_story_circle": [
                    {
                        "phase": phase['phase_name'],
                        "description": phase['description'] or ""
                    }
                    for phase in phases
                ],
                "current_phase": current_phase['phase_name'],
                "next_phase": self._get_next_phase(current_phase['phase_name']),
                "events": [ed['event'] for ed in events_dialogues],
                "inner_dialogues": [ed['inner_dialogue'] for ed in events_dialogues],
                "dynamic_context": {
                    "current_event": events_dialogues[0]['event'] if events_dialogues else "",
                    "current_inner_dialogue": events_dialogues[0]['inner_dialogue'] if events_dialogues else "",
                    "next_event": events_dialogues[1]['event'] if len(events_dialogues) > 1 else ""
                }
            }

            return {"narrative": narrative}

        except Exception as e:
            logger.error(f"Error getting current narrative: {e}")
            raise

    def _get_next_phase(self, current_phase):
        """Helper method to determine the next phase"""
        phases = ["You", "Need", "Go", "Search", "Find", "Take", "Return", "Change"]
        current_index = phases.index(current_phase)
        next_index = (current_index + 1) % len(phases)
        return phases[next_index]

    def get_current_context(self):
        """Get the current story circle context"""
        try:
            # Load and validate story circle
            story_circle = self.db.get_story_circle()
            logger.info(f"Retrieved story circle: {json.dumps(story_circle, indent=2)}")
            
            if not story_circle:
                logger.error("No story circle found")
                return {
                    'current_event': '',
                    'current_inner_dialogue': ''
                }
            
            # Validate required fields
            required_fields = ['id', 'current_phase_number', 'dynamic_context']
            missing_fields = [f for f in required_fields if f not in story_circle]
            if missing_fields:
                logger.error(f"Story circle missing required fields: {missing_fields}")
                logger.info(f"Story circle structure: {json.dumps(story_circle, indent=2)}")
                return {
                    'current_event': '',
                    'current_inner_dialogue': ''
                }
            
            # Get current phase events with proper arguments
            try:
                events_dialogues = self.db.get_events_dialogues(
                    story_circle_id=story_circle["id"],
                    phase_number=story_circle["current_phase_number"]
                )
                logger.info(f"Retrieved events_dialogues: {json.dumps(events_dialogues, indent=2)}")
                
            except Exception as e:
                logger.error(f"Error getting events and dialogues: {e}")
                logger.error(f"Story circle ID: {story_circle.get('id')}")
                logger.error(f"Current phase number: {story_circle.get('current_phase_number')}")
                return {
                    'current_event': '',
                    'current_inner_dialogue': ''
                }
            
            if not events_dialogues:
                logger.warning("No events/dialogues found for current phase")
                return {
                    'current_event': '',
                    'current_inner_dialogue': ''
                }
            
            # Get current event from dynamic context
            current_event = story_circle["dynamic_context"].get("current_event")
            if not current_event:
                logger.warning("No current event in dynamic context")
                return {
                    'current_event': '',
                    'current_inner_dialogue': ''
                }
            
            # Find matching dialogue
            try:
                current_dialogue = next(
                    (e["dialogue"] for e in events_dialogues if e["event"] == current_event),
                    ''
                )
                logger.info(f"Found current event: {current_event}")
                logger.info(f"Found current dialogue: {current_dialogue}")
                
            except Exception as e:
                logger.error(f"Error finding current dialogue: {e}")
                logger.error(f"Current event: {current_event}")
                logger.error(f"Available events: {[e.get('event') for e in events_dialogues]}")
                return {
                    'current_event': '',
                    'current_inner_dialogue': ''
                }
            
            return {
                'current_event': current_event,
                'current_inner_dialogue': current_dialogue
            }
            
        except Exception as e:
            logger.error(f"Error getting current context: {e}")
            logger.exception("Full traceback:")
            return {
                'current_event': '',
                'current_inner_dialogue': ''
            }

    def progress_narrative(self):
        """Main function to progress the narrative"""
        try:
            # Load current story circle from database
            story_circle = self.db.get_story_circle()
            
            # Log the received story circle for debugging
            logger.info(f"Received story circle: {json.dumps(story_circle, indent=2)}")
            
            # Validate story circle structure
            if not story_circle:
                logger.error("Story circle is None or empty")
                return self.update_story_circle()
            
            # Log expected vs actual structure
            expected_keys = ['id', 'current_phase', 'current_phase_number', 'is_current', 
                            'phases', 'events', 'dialogues', 'dynamic_context']
            actual_keys = list(story_circle.keys())
            
            logger.info(f"Expected keys: {expected_keys}")
            logger.info(f"Actual keys: {actual_keys}")
            
            missing_keys = [key for key in expected_keys if key not in actual_keys]
            if missing_keys:
                logger.error(f"Story circle missing required keys: {missing_keys}")
                return self.update_story_circle()
            
            # Validate dynamic context
            if not story_circle.get('dynamic_context'):
                logger.error("Missing dynamic_context in story circle")
                logger.info(f"Story circle structure: {json.dumps(story_circle, indent=2)}")
                return self.update_story_circle()
            
            current_event = story_circle['dynamic_context'].get('current_event')
            logger.info(f"Current event: {current_event}")
            
            if not current_event:
                # No current event, start with first event
                if story_circle.get('events'):
                    logger.info("No current event found, initializing with first event")
                    story_circle['dynamic_context'].update({
                        'current_event': story_circle['events'][0],
                        'current_inner_dialogue': story_circle['dialogues'][0],
                        'next_event': story_circle['events'][1] if len(story_circle['events']) > 1 else ""
                    })
                    self.db.update_story_circle_state(story_circle)
                    return story_circle
                else:
                    logger.error("No events found in story circle")
                    logger.info(f"Story circle events: {story_circle.get('events')}")
                    return self.update_story_circle()
            
            # Progress to next event
            return self.progress_to_next_event(story_circle)
            
        except Exception as e:
            logger.error(f"Error progressing narrative: {str(e)}")
            logger.exception("Full traceback:")
            raise

    def complete_circle(self, story_circle):
        """Complete current circle and start new one"""
        try:
            logger.info(f"Completing story circle {story_circle['id']}")
            
            # 1. Set all phases of current circle to not current
            try:
                # Add explicit WHERE clause for the current story circle
                self.db.client.table('story_phases')\
                    .update({'is_current': False})\
                    .eq('story_circle_id', story_circle["id"])\
                    .execute()
                logger.info(f"Set all phases to not current for story circle {story_circle['id']}")
            except Exception as e:
                logger.error(f"Error updating phase statuses: {e}")
                raise
            
            # 2. Set current circle as completed
            self.db.update_story_circle(
                story_circle["id"], 
                {
                    "is_current": False,
                    "completed_at": datetime.now().isoformat()
                }
            )
            
            # 3. Generate summary with validation
            circles_memory = self.load_circles_memory()
            summary = self.generate_circle_summary(story_circle, circles_memory)
            
            if not summary or "memories" not in summary:
                logger.error("Invalid summary format")
                raise Exception("Summary generation failed")
            
            # 4. Save memory
            success = self.db.insert_circle_memories(story_circle["id"], summary["memories"])
            if not success:
                logger.error("Failed to save circle memories")
                raise Exception("Memory insertion failed")
            logger.info(f"Successfully saved memories: {summary['memories']}")
            
            # 5. Create new story circle
            new_circle = self.db.create_story_circle()
            if not new_circle:
                logger.error("Failed to create new story circle")
                raise Exception("Story circle creation failed")
            
            logger.info(f"Created new story circle {new_circle['id']}")
            
            # 6. Generate initial content for new circle
            updated_circle = self.update_story_circle()
            if not updated_circle:
                logger.error("Failed to update new story circle")
                raise Exception("Story circle update failed")
        
            logger.info("Successfully completed story circle cycle")
            return updated_circle
            
        except Exception as e:
            logger.error(f"Error completing circle: {e}")
            logger.exception("Full traceback:")
            raise

    def _transform_ai_response(self, ai_response, story_circle):
        """Transform AI response into story circle format"""
        try:
            narrative = ai_response.get('narrative', {})
            
            # Preserve existing story circle structure
            transformed = {
                'id': story_circle['id'],
                'is_current': story_circle['is_current'],
                'current_phase': story_circle['current_phase'],  # Keep existing phase
                'current_phase_number': story_circle['current_phase_number'],  # Keep existing phase number
                'phases': story_circle['phases'],  # Preserve existing phases
                'events': narrative.get('events', []),
                'dialogues': narrative.get('inner_dialogues', []),
                'dynamic_context': {
                    'current_event': narrative.get('events', [])[0] if narrative.get('events') else '',
                    'current_inner_dialogue': narrative.get('inner_dialogues', [])[0] if narrative.get('inner_dialogues') else '',
                    'next_event': narrative.get('events', [])[1] if len(narrative.get('events', [])) > 1 else ''
                }
            }
            
            # Validate required fields
            required_fields = ['id', 'current_phase', 'current_phase_number', 'phases', 
                             'events', 'dialogues', 'dynamic_context']
            if not all(field in transformed for field in required_fields):
                logger.error(f"Missing required fields: {[f for f in required_fields if f not in transformed]}")
                return None
            
            # Ensure events and dialogues are properly initialized
            if transformed['events'] and not transformed['dynamic_context']['current_event']:
                transformed['dynamic_context'].update({
                    'current_event': transformed['events'][0],
                    'current_inner_dialogue': transformed['dialogues'][0],
                    'next_event': transformed['events'][1] if len(transformed['events']) > 1 else ''
                })
            
            return transformed
            
        except Exception as e:
            logger.error(f"Error transforming AI response: {e}")
            logger.exception("Full traceback:")
            return None

    def _reconcile_story_states(self, memory_state, db_state):
        """Reconcile differences between memory and database states"""
        try:
            # Log initial state
            logger.info("Beginning state reconciliation")
            logger.debug(f"Memory state: {json.dumps(memory_state, indent=2)}")
            logger.debug(f"Database state: {json.dumps(db_state, indent=2)}")

            # Update critical fields from database state
            fields_to_sync = {
                'current_phase': 'Current phase',
                'current_phase_number': 'Phase number',
                'events': 'Events',
                'dialogues': 'Dialogues'
            }

            for field, description in fields_to_sync.items():
                if memory_state.get(field) != db_state.get(field):
                    logger.warning(f"{description} mismatch detected - updating from database")
                    memory_state[field] = db_state[field]

            # Special handling for dynamic context
            if memory_state.get('events'):
                memory_state['dynamic_context'] = {
                    'current_event': memory_state['events'][0],
                    'current_inner_dialogue': memory_state['dialogues'][0],
                    'next_event': memory_state['events'][1] if len(memory_state['events']) > 1 else ''
                }
            else:
                # If no events, initialize empty context but preserve structure
                memory_state['dynamic_context'] = {
                    'current_event': '',
                    'current_inner_dialogue': '',
                    'next_event': ''
                }

            # Ensure phase descriptions are consistent
            if 'phases' in memory_state and 'phases' in db_state:
                for mem_phase, db_phase in zip(memory_state['phases'], db_state['phases']):
                    if mem_phase.get('description') != db_phase.get('description'):
                        logger.warning(f"Phase description mismatch for phase {mem_phase.get('phase')}")
                        mem_phase['description'] = db_phase['description']

            # Save reconciled state
            self.db.update_story_circle_state(memory_state)
            logger.info("State reconciliation completed")

            return memory_state

        except Exception as e:
            logger.error(f"Error reconciling states: {e}")
            logger.exception("Full traceback:")
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