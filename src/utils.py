# src/utils.py

import json
import os
from typing import Any, Optional
import time

def save_cookies(cookies: list, filename: str) -> None:
    """Save cookies to a file"""
    try:
        with open(filename, 'w') as f:
            json.dump(cookies, f)
    except Exception as e:
        print(f"Error saving cookies: {e}")

def load_cookies(filename: str) -> Optional[list]:
    """Load cookies from a file"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading cookies: {e}")
    return None

def get_env_variable(key: str) -> str:
    """Get environment variable with proper error handling and whitespace cleaning"""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} not set")
    # Strip whitespace and validate
    value = value.strip()
    if not value:
        raise ValueError(f"Environment variable {key} is empty")
    return value
