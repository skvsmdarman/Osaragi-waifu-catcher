from telegram.ext import Application
from shivu import LOG_CHANNEL_ID

async def log_activity(application: Application, message: str):
    """
    Sends a formatted message to the log channel.
    """
    if not LOG_CHANNEL_ID:
        print(f"Log (LOG_CHANNEL_ID not set): {message}")
        return

    try:
        await application.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=message,
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Failed to send log message to channel {LOG_CHANNEL_ID}. Error: {e}")
        print(f"Log Message: {message}")
