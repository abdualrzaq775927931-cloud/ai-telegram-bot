import logging
import os
import sys

# Add the current directory to the Python path to resolve ModuleNotFoundError
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from bot.config.settings import BOT_TOKEN, ADMIN_IDS
from bot.database.db_manager import init_db
from bot.handlers.base_handlers import start, profile, leaderboard
from bot.handlers.admin_handlers import (
    admin_panel,
    start_broadcast,
    perform_broadcast,
    BROADCAST_MESSAGE,
    is_admin
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Initialize Database
    init_db()
    
    # Create the Application
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # Callback Handlers
    application.add_handler(CallbackQueryHandler(profile, pattern="profile"))
    application.add_handler(CallbackQueryHandler(leaderboard, pattern="leaderboard"))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="admin_panel"))
    
    # Admin Broadcast Conversation Handler
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern="admin_broadcast")],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, perform_broadcast)]
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    application.add_handler(broadcast_conv)
    
    # Start the Bot
    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
