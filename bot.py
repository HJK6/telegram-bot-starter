"""
Telegram Bot — the user-facing interface.

Connects Telegram to the orchestrator for message routing
and agent management. Also serves the admin dashboard.

Usage:
  python bot.py
"""

import asyncio
import logging
import threading

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID
from orchestrator import Orchestrator

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")

orchestrator = Orchestrator()


# ── Auth ────────────────────────────────────────────────────────

def owner_only(func):
    """Restrict to OWNER_CHAT_ID. Set to 0 in .env to allow everyone."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if OWNER_CHAT_ID and update.effective_chat.id != OWNER_CHAT_ID:
            await update.message.reply_text("Not authorized.")
            return
        return await func(update, context)
    return wrapper


# ── Telegram → Orchestrator callback ───────────────────────────

_app_ref = None  # set after app is built


async def send_to_telegram(agent_id: str, text: str):
    """Callback: orchestrator calls this to send a message to the user."""
    if _app_ref and OWNER_CHAT_ID:
        # Chunk long messages (Telegram limit: 4096)
        for i in range(0, len(text), 4000):
            await _app_ref.bot.send_message(
                chat_id=OWNER_CHAT_ID,
                text=text[i : i + 4000],
            )


orchestrator.set_message_callback(send_to_telegram)


# ── Command handlers ────────────────────────────────────────────

@owner_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot online. Commands:\n\n"
        "/status  — active agents and their tasks\n"
        "/agents  — list all agents with IDs\n"
        "/new <goal>  — start a new agent\n"
        "/stop <id>  — stop an agent\n"
        "/delete <id>  — delete an agent\n"
        "/reset  — stop all agents\n"
        "/help  — show this message\n\n"
        "Or just send a message — it will be routed to the right agent."
    )


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(orchestrator.get_status_text())


@owner_only
async def cmd_agents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(orchestrator.get_agents_text())


@owner_only
async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /new <goal description>")
        return
    goal = " ".join(context.args)
    agent = orchestrator.create_agent(goal)
    await update.message.reply_text(
        f"Agent created: [{agent.short_id}] {agent.title}"
    )


@owner_only
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stop <agent_id_prefix>")
        return
    prefix = context.args[0].lower()
    for agent in orchestrator.get_all_agents():
        if agent.agent_id.startswith(prefix):
            orchestrator.stop_agent(agent.agent_id)
            await update.message.reply_text(f"Stopped: [{agent.short_id}] {agent.title}")
            return
    await update.message.reply_text(f"No agent found with prefix: {prefix}")


@owner_only
async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delete <agent_id_prefix>")
        return
    prefix = context.args[0].lower()
    for agent in orchestrator.get_all_agents():
        if agent.agent_id.startswith(prefix):
            orchestrator.delete_agent(agent.agent_id)
            await update.message.reply_text(f"Deleted: [{agent.short_id}] {agent.title}")
            return
    await update.message.reply_text(f"No agent found with prefix: {prefix}")


@owner_only
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = 0
    for agent in orchestrator.get_active_agents():
        orchestrator.stop_agent(agent.agent_id)
        count += 1
    await update.message.reply_text(f"Stopped {count} agent(s).")


@owner_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


@owner_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route plain text messages through the orchestrator."""
    text = update.message.text
    if not text:
        return
    await orchestrator.route_message(text, sender="user")


# ── Main ────────────────────────────────────────────────────────

def start_dashboard_in_thread():
    """Run the Flask dashboard in a background thread."""
    try:
        from dashboard import create_app
        app = create_app(orchestrator)
        # Suppress Flask request logs in the main console
        flask_log = logging.getLogger("werkzeug")
        flask_log.setLevel(logging.WARNING)
        from config import DASHBOARD_HOST, DASHBOARD_PORT
        log.info(f"Dashboard: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
        app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, use_reloader=False)
    except Exception as e:
        log.error(f"Dashboard failed to start: {e}")


def main():
    global _app_ref

    # Start dashboard in background thread
    dash_thread = threading.Thread(target=start_dashboard_in_thread, daemon=True)
    dash_thread.start()

    # Build Telegram bot
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    _app_ref = app

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("agents", cmd_agents))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot starting (Telegram polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
