# src/config.py

import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

class Config:
    # API Keys
    GLHF_API_KEY = os.getenv('GLHF_API_KEY')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    TWITTER_USERNAME = os.getenv('TWITTER_USERNAME')
    TWITTER_PASSWORD = os.getenv('TWITTER_PASSWORD')
    TWITTER_EMAIL = os.getenv('TWITTER_EMAIL')

    # OpenAI Client
    openai_client = OpenAI(
        api_key=GLHF_API_KEY,
        base_url=os.getenv('OPENAI_BASE_URL', 'https://glhf.chat/api/openai/v1')
    )

    # Bot Configuration
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'fwogaibot')
    DISCORD_BOT_USERNAME = os.getenv('DISCORD_BOT_USERNAME', 'Fwog-AI')

    # Model Configuration 1
    AI_MODEL = os.getenv('MODEL', 'hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF')
    TEMPERATURE = float(os.getenv('TEMPERATURE', '0.7'))
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://glhf.chat/api/openai/v1')

    #Model Configuration 2
    AI_MODEL2 = os.getenv('MODEL', 'hf:google/gemma-2-9b-it')
    TEMPERATURE = float(os.getenv('TEMPERATURE', '0.7'))
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://glhf.chat/api/openai/v1')


    # Conversation Settings
    MAX_MEMORY = int(os.getenv('MAX_MEMORY', '1'))
