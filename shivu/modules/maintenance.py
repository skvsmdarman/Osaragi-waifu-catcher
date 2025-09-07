from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from shivu import application, OWNER_ID, bot_settings_collection

DEFAULT_MAINTENANCE_MESSAGE = "Heeey! Osaragi is taking a quick nap for some maintenance 😴. I'll be back in a flash, so please try again in a little bit! ✨"

async def maintenance(update: Update, context: CallbackContext) -> None:
    """
    Enable, disable, or set a custom maintenance message for the bot.
    Usage: /maintenance <on|off> [custom message]
    """
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("You are not authorized to use this command. Only the Owner can.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /maintenance <on|off> [custom message]")
        return

    mode = args[0].lower()

    if mode == "on":
        custom_message = ' '.join(args[1:]) if len(args) > 1 else DEFAULT_MAINTENANCE_MESSAGE
        await bot_settings_collection.update_one(
            {'setting': 'maintenance'},
            {'$set': {'enabled': True, 'message': custom_message}},
            upsert=True
        )
        await update.message.reply_text(f"Okay! I've put up the 'do not disturb' sign! Osaragi is now in maintenance mode. 🛠️\n\nI'll be telling users: \"{custom_message}\"")
    elif mode == "off":
        await bot_settings_collection.update_one(
            {'setting': 'maintenance'},
            {'$set': {'enabled': False}},
            upsert=True
        )
        await update.message.reply_text("Alright, I'm back! Maintenance is over. Let the waifu catching resume! 🎉")
    else:
        await update.message.reply_text("Invalid argument. Use 'on' or 'off'.")

async def get_maintenance_status():
    """Helper to get maintenance status from DB."""
    return await bot_settings_collection.find_one({'setting': 'maintenance'})

MAINTENANCE_HANDLER = CommandHandler('maintenance', maintenance, block=False)
application.add_handler(MAINTENANCE_HANDLER)
