# Multi-Platform AI Bot

A versatile AI-powered bot that operates across Twitter, Discord, Telegram platforms. The bot uses advanced language models to generate contextual responses while maintaining a unique personality.

## Features

- 🤖 Multi-platform support (Twitter, Discord, Telegram)
- 🧠 AI-powered responses using advanced language models
- 💾 Persistent memory system for context-aware conversations
- 📚 Story circle narrative progression
- 🔄 Session management for Twitter interactions
- 🗄️ Supabase database integration for persistent storage

## Prerequisites

- Python 3.8+
- Selenium WebDriver (for Twitter bot)
- API keys for respective platforms
- GLHF API access
- Supabase account and project

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Create and activate a virtual environment:
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up Selenium WebDriver (for Twitter bot):
   - Download [ChromeDriver](https://sites.google.com/chromium.org/driver/) matching your Chrome version
   - Add ChromeDriver to your system PATH

5. Configure environment variables:
```bash
cp .env.template .env
```

## Configuration

1. Edit the `.env` file with your credentials:
   - Get GLHF API key from [GLHF Chat](https://glhf.chat)
   - Create a [Telegram Bot](https://core.telegram.org/bots#creating-a-new-bot) and get the token
   - Set up a [Discord Application](https://discord.com/developers/applications) and get the bot token
   - Add your Twitter credentials
   - Set up Supabase (see Database Setup below)

2. Configure bot settings:
   - Adjust model parameters in `.env` if needed
   - Set memory limits and other preferences
   - Customize bot usernames if desired

## Database Setup

1. Create a Supabase Project:
   - Go to [Supabase](https://supabase.com) and create a new project
   - Note down your project URL and anon/public key

2. Set up required tables:
```sql
-- Create memories table
create table memories (
  id bigint generated by default as identity primary key,
  content text not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create story_circle table
create table story_circle (
  id bigint generated by default as identity primary key,
  narrative jsonb not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create circle_memories table
create table circle_memories (
  id bigint generated by default as identity primary key,
  memories jsonb not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create emotion_formats table
create table emotion_formats (
  id bigint generated by default as identity primary key,
  format text not null,
  description text not null
);

-- Create length_formats table
create table length_formats (
  id bigint generated by default as identity primary key,
  format text not null,
  description text not null
);

-- Create topics table
create table topics (
  id bigint generated by default as identity primary key,
  topic text not null
);

-- Create processed_tweets table
create table processed_tweets (
  id bigint generated by default as identity primary key,
  tweet_id text not null unique
);
```

3. Configure Database Access:
   - Add your Supabase URL and anon key to `.env`:
   ```
   SUPABASE_URL=your_project_url
   SUPABASE_KEY=your_anon_key
   ```
   - The URL looks like: `https://[project-ref].supabase.co`
   - The key starts with `eyJ...`

4. Initialize Database (Optional):
```bash
python migration_script.py
```
This will populate initial data for emotion formats, length formats, and other required tables.

## Running the Bots

### Running All Bots
```bash
python main.py
```

### Running Individual Bots
```bash
# Twitter Bot only..
python main.py -- bots twitter

# Discord Bot only
python main.py --bots discord

# Telegram Bot only
python main.py --bots telegram
```

### Development Mode
```bash
# Run with debug logging
python main.py --debug
```

## Bot Features and Commands

### Discord Commands
- `!help` - Show available commands
- `!chat [message]` - Chat with the bot
- `!memory` - View bot's memories

### Telegram Commands
- `/start` - Begin interaction
- `/chat [message]` - Chat with the bot
- `/help` - Show available commands

### Twitter Features
- Auto-replies to mentions
- Periodic tweet generation
- Context-aware conversations
- Session management

## Project Structure
```
├── src/
│   ├── twitter_bot/
│   │   ├── authenticator.py    # Twitter authentication
│   │   └── tweets.py          # Tweet management
│   ├── discord_bot/
│   │   └── discord_bot.py     # Discord bot implementation
│   ├── telegram_bot/
│   │   └── telegram_bot.py    # Telegram bot implementation
│   ├── ai_generator.py        # AI response generation
│   ├── config.py             # Configuration management
│   ├── memory_processor.py   # Memory management
│   └── utils.py             # Utility functions
├── data/
│   └── processed_tweets.txt  # Tweet history
├── requirements.txt         # Python dependencies
├── .env.template           # Environment template
└── main.py                # Entry point
```

## Troubleshooting

### Common Issues

1. Twitter Authentication:
```bash
# If sessions are not working, try:
python main.py --twitter --reset-session
```

2. Discord Connection:
- Ensure bot has proper permissions in server
- Check if token is valid
- Verify internet connection

3. Telegram Issues:
- Confirm bot token is active
- Check bot privacy settings

### Logs
Check logs for detailed error information:
```bash
tail -f logs/bot.log
```

## Contributing

1. Fork the repository
2. Create your feature branch:
```bash
git checkout -b feature/amazing-feature
```
3. Commit your changes:
```bash
git commit -m 'Add amazing feature'
```
4. Push to the branch:
```bash
git push origin feature/amazing-feature
```
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- GLHF Chat for AI API access
- OpenAI for model architectures
- Selenium for web automation
- Discord.py, python-telegram-bot for platform SDKs

## Database Management Commands

### Clear Database
To clear all data from the database tables:
```bash
python migrations/clear_database.py
```

### Run Database Migration
To migrate story circle data to Supabase:
```bash
python migrations/story_circle_supabase_migration.py
```

### Run Tests
To run the story progression tests:
```bash
python -m pytest tests/test_story_progression.py -v
```

### Database Management Flow
When setting up or resetting the database, follow this order:
1. Clear the database first
2. Run the migration
3. Run tests to verify everything is working

Example:
```bash
# Clear all data
python migrations/clear_database.py

# Run migration
python migrations/story_circle_supabase_migration.py

# Run tests
python -m tests.test_story_progression

Note: Make sure you have all required environment variables set in your `.env` file before running these commands.