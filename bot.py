"""
Telegram Bot Starter
A modular Telegram bot with pluggable abilities.

Setup:
  1. pip install python-telegram-bot requests beautifulsoup4 httpx
  2. Copy .env.example to .env and fill in your bot token
  3. python bot.py
"""

import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from abilities.scraper import scrape_url, summarize_page
from abilities.weather import get_weather
from abilities.reminders import schedule_reminder

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USERS = {int(uid) for uid in os.getenv("ALLOWED_USER_IDS", "").split(",") if uid.strip()}


# ── Auth decorator ──────────────────────────────────────────────
def authorized(func):
    """Only lets through users in ALLOWED_USER_IDS (if set)."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if ALLOWED_USERS and update.effective_user.id not in ALLOWED_USERS:
            await update.message.reply_text("Not authorized.")
            return
        return await func(update, context)
    return wrapper


# ── Command handlers ────────────────────────────────────────────
@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! I'm your bot. Commands:\n"
        "/scrape <url> - Scrape a webpage\n"
        "/weather <city> - Current weather\n"
        "/remind <minutes> <message> - Set a reminder\n"
        "/help - Show this message"
    )


@authorized
async def cmd_scrape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /scrape <url>")
        return
    url = context.args[0]
    await update.message.reply_text(f"Scraping {url}...")
    try:
        result = scrape_url(url)
        # Telegram messages max 4096 chars
        for i in range(0, len(result), 4000):
            await update.message.reply_text(result[i : i + 4000])
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


@authorized
async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /weather <city>")
        return
    city = " ".join(context.args)
    try:
        result = get_weather(city)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


@authorized
async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /remind <minutes> <message>")
        return
    try:
        minutes = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Minutes must be a number.")
        return
    message = " ".join(context.args[1:])
    chat_id = update.effective_chat.id
    schedule_reminder(context.job_queue, chat_id, minutes, message)
    await update.message.reply_text(f"Reminder set for {minutes} minute(s).")


@authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


@authorized
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback for plain text messages."""
    text = update.message.text
    await update.message.reply_text(
        f"I got your message: \"{text}\"\n"
        "Use /help to see what I can do."
    )


# ── Main ────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("scrape", cmd_scrape))
    app.add_handler(CommandHandler("weather", cmd_weather))
    app.add_handler(CommandHandler("remind", cmd_remind))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
