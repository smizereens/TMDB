import logging
import os
import asyncio # Import asyncio for gather
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler # Import CallbackQueryHandler

# Import handlers from bot_logic
import bot_logic

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def main() -> None:
    """Start the bot."""
    # Load environment variables from .env file
    load_dotenv()
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TMDB_API_KEY = os.getenv('TMDB_API_KEY') # Load TMDB key to check if it exists

    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables. Exiting.")
        return
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY not found in environment variables. Check .env file, but continuing...")
        # Allow continuing but API calls will fail

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Register Handlers ---
    # Basic commands
    application.add_handler(CommandHandler("start", bot_logic.start))
    application.add_handler(CommandHandler("help", bot_logic.help_command))
    application.add_handler(CommandHandler("search", bot_logic.search_command))
    application.add_handler(CommandHandler("popular", bot_logic.popular_command))
    application.add_handler(CommandHandler("toprated", bot_logic.toprated_command))
    application.add_handler(CommandHandler("upcoming", bot_logic.upcoming_command))

    # --- Conversation Handlers ---
    application.add_handler(bot_logic.discover_conv_handler)
    application.add_handler(bot_logic.search_conv_handler) # Add search conversation

    # --- Callback Query Handlers ---
    application.add_handler(bot_logic.pagination_handler) # Handles next/prev buttons

    # --- Message Handlers for Buttons ---
    # These should be added after CommandHandlers and ConversationHandlers
    # to allow commands like /start to take precedence over button text
    application.add_handler(bot_logic.popular_button_handler)
    application.add_handler(bot_logic.toprated_button_handler)
    application.add_handler(bot_logic.upcoming_button_handler)
    application.add_handler(bot_logic.help_button_handler)

    # Note: The cancel command is registered within the ConversationHandler's fallbacks

    logger.info("Bot handlers registered.")

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot polling...")
    # Pre-load caches before starting polling (optional, but good practice)
    # asyncio.run(bot_logic.ensure_api_config_cached()) # Already called in start handler
    # asyncio.run(bot_logic.ensure_genres_cached()) # Already called in start handler
    application.run_polling()
    logger.info("Bot stopped.")

if __name__ == "__main__":
    # Use asyncio.run() if your top-level functions are async
    # For run_polling, it's synchronous at the top level.
    main()
