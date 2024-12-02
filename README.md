# Multi-Platform AI Bot

A versatile AI-powered bot that operates across Twitter, Discord, Telegram platforms. The bot uses advanced language models to generate contextual responses while maintaining a unique personality.

## Features

- 🤖 Multi-platform support (Twitter, Discord, Telegram)
- 🧠 AI-powered responses using advanced language models
- 💾 Persistent memory system for context-aware conversations
- 📚 Story circle narrative progression
- 🔄 Session management for Twitter interactions

## Prerequisites

- Python 3.8+
- Selenium WebDriver (for Twitter bot)
- API keys for respective platforms
- GLHF API access

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

2. Configure bot settings:
   - Adjust model parameters in `.env` if needed
   - Set memory limits and other preferences
   - Customize bot usernames if desired

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