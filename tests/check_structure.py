import os
import sys

def check_project_structure():
    """Verify project structure is correct for testing"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    required_files = [
        'pytest.ini',
        'tests/conftest.py',
        'tests/test_story_circle_integration.py',
        'src/__init__.py',
        'src/story_circle_manager.py',
        'src/database/supabase_client.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = os.path.join(project_root, file_path)
        if not os.path.exists(full_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("Missing required files:")
        for file in missing_files:
            print(f"  - {file}")
        sys.exit(1)
    
    print("Project structure verified successfully!")

if __name__ == "__main__":
    check_project_structure() 