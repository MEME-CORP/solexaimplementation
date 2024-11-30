# main.py

import sys
import threading
import argparse
import os
from pathlib import Path
import signal
import asyncio
import time
from telegram import Update
from telegram.ext import Application
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Global variables for thread management
running = True
twitter_thread = None
telegram_thread = None
discord_thread = None

def signal_handler(signum, frame):
    """Handle shutdown signals in main thread"""
    global running, twitter_thread, telegram_thread, discord_thread
    print(f"\nReceived signal {signum}. Starting graceful shutdown...")
    running = False
    
    # Wait for threads to finish
    threads_to_check = [
        (twitter_thread, "Twitter bot"),
        (telegram_thread, "Telegram bot"),
        (discord_thread, "Discord bot")
    ]
    
    for thread, name in threads_to_check:
        if thread and thread.is_alive():
            print(f"Waiting for {name} to shut down...")
            thread.join(timeout=30)
            if thread.is_alive():
                print(f"{name} shutdown timed out!")
    
    print("Main thread shutting down...")
    sys.exit(0)

def setup_signal_handlers():
    """Setup signal handlers in main thread"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def run_twitter_bot():
    global running
    from src.twitter_bot.twitter_bot import TwitterBot
    
    try:
        # Create bot instance without signal handlers since we're in a thread
        bot = TwitterBot(handle_signals=False)
        # Create an event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run the bot's async function
            loop.run_until_complete(bot.run())
        except Exception as e:
            print(f"Twitter bot error: {e}")
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    except Exception as e:
        print(f"Twitter bot error: {e}")
    finally:
        print("Twitter bot has stopped.")

def run_telegram_bot():
    """Run the Telegram bot in the main thread"""
    try:
        from src.telegram_bot.telegram_bot import TelegramBot
        
        # Create and setup bot
        bot = TelegramBot()
        application = bot.setup()
        
        print("Starting Telegram bot...")
        # Run the application in the main thread
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"Error in Telegram bot: {e}")

def run_discord_bot():
    """Run the Discord bot"""
    global running
    try:
        from src.discord_bot.discord_bot import DiscordBot
        
        # Create and setup bot
        bot = DiscordBot()
        print("Starting Discord bot...")
        bot.run_bot()
        
    except Exception as e:
        print(f"Error in Discord bot: {e}")
    finally:
        print("Discord bot has stopped.")

def main():
    global twitter_thread, discord_thread, running
    parser = argparse.ArgumentParser()
    parser.add_argument('--bots', nargs='+', choices=['twitter', 'telegram', 'discord'], 
                       help='Specify which bots to run')
    args = parser.parse_args()

    if not args.bots:
        parser.print_help()
        return

    # Set up signal handlers only in main thread
    setup_signal_handlers()

    try:
        if 'twitter' in args.bots:
            twitter_thread = threading.Thread(target=run_twitter_bot, daemon=True)
            twitter_thread.start()
            print("Twitter bot thread started.")

        if 'discord' in args.bots:
            discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
            discord_thread.start()
            print("Discord bot thread started.")

        if 'telegram' in args.bots:
            # Run Telegram bot in main thread
            run_telegram_bot()
        else:
            # Keep main thread alive for other bots
            while running:
                time.sleep(1)

    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        running = False
        print("Initiating shutdown sequence...")

        if twitter_thread and twitter_thread.is_alive():
            print("Waiting for Twitter bot to shut down...")
            twitter_thread.join(timeout=30)
            if twitter_thread.is_alive():
                print("Twitter bot shutdown timed out!")

        if discord_thread and discord_thread.is_alive():
            print("Waiting for Discord bot to shut down...")
            discord_thread.join(timeout=30)
            if discord_thread.is_alive():
                print("Discord bot shutdown timed out!")

        print("Main thread shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()
