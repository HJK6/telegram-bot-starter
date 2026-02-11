"""
Configuration — loads from .env, provides defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "0"))

# Dashboard
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "change-me-in-production")

# Database
DB_PATH = os.getenv("DB_PATH", "bot.db")

# Agent defaults
MAX_AGENTS = int(os.getenv("MAX_AGENTS", "10"))
AGENT_IDLE_TIMEOUT = int(os.getenv("AGENT_IDLE_TIMEOUT", "3600"))  # seconds
