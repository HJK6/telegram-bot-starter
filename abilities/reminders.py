"""
Reminders ability — schedule one-shot delayed messages using
python-telegram-bot's built-in job queue.
"""

from telegram.ext import CallbackContext


async def _send_reminder(context: CallbackContext):
    job = context.job
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"Reminder: {job.data}",
    )


def schedule_reminder(job_queue, chat_id: int, minutes: int, message: str):
    """Schedule a reminder that fires once after `minutes` minutes."""
    job_queue.run_once(
        _send_reminder,
        when=minutes * 60,
        chat_id=chat_id,
        data=message,
    )
