import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Database URL (Default: SQLite for easy deployment)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///poll_bot.db")

# Super Admins (Telegram User IDs)
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]

# Log Channel ID (Optional)
LOG_CHANNEL = os.getenv("LOG_CHANNEL")

# Anti-Spam Settings (seconds between requests)
SPAM_THRESHOLD = 1.5

# Bot Version
VERSION = "1.1.0"
