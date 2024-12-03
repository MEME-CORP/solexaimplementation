import json
from src.database.supabase_client import DatabaseService

def migrate_story_circle():
    # Load JSON data
    with open('data/story_circle.json', 'r') as f:
        story_data = json.load(f)

    # Initialize database service
    db = DatabaseService()

    # Migrate data
    try:
        # Insert into story_circle table
        result = db.client.table('story_circle').insert({
            'narrative': {
                'events': story_data['narrative']['events'],
                'next_phase': story_data['narrative']['next_phase'],
                'current_phase': story_data['narrative']['current_phase'],
                'dynamic_context': story_data['narrative']['dynamic_context'],
                'inner_dialogues': story_data['narrative']['inner_dialogues']
            }
        }).execute()

        story_circle_id = result.data[0]['id']

        # Insert into story_phases table
        for phase in story_data['narrative']['current_story_circle']:
            db.client.table('story_phases').insert({
                'story_circle_id': story_circle_id,
                'phase': phase['phase'],
                'description': phase['description']
            }).execute()

        print("Migration successful!")

    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate_story_circle()