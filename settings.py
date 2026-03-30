import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Database URL (Default: SQLite for easy deployment)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///poll_bot.db")

# Super Admins (Telegram User IDs)
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]

# Bot Version
VERSION = "1.0.0"
