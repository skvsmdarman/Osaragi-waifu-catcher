from telegram import Update
from telegram.ext import CallbackContext
from shivu import OWNER_ID

def owner_only(func):
    """Decorator to restrict command usage to the bot owner."""
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if str(update.effective_user.id) != OWNER_ID:
            await update.message.reply_text("You are not authorized to use this command.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
