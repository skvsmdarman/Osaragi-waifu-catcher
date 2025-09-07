import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, CallbackContext

from shivu import application, OWNER_ID, bot_settings_collection

# --- Constants and Database ---
BOT_SETTINGS_COLLECTION = bot_settings_collection
SETTING_NAME = 'catch_limit'

# --- Conversation states ---
SET_FREQUENCY = 1

# --- Helper Functions ---

async def get_catch_limit_settings():
    """Fetches catch limit settings from the database."""
    settings = await BOT_SETTINGS_COLLECTION.find_one({'setting': SETTING_NAME})
    if not settings:
        # Default settings
        return {'frequency': 100, 'include_stickers': False, 'include_commands': False}
    return settings

async def update_catch_limit_setting(key, value):
    """Updates a specific catch limit setting in the database."""
    await BOT_SETTINGS_COLLECTION.update_one(
        {'setting': SETTING_NAME},
        {'$set': {key: value}},
        upsert=True
    )

async def build_settings_keyboard():
    """Builds the inline keyboard with current settings."""
    settings = await get_catch_limit_settings()

    freq = settings.get('frequency', 100)
    stickers_enabled = settings.get('include_stickers', False)
    commands_enabled = settings.get('include_commands', False)

    keyboard = [
        [InlineKeyboardButton(f"Message Frequency: {freq}", callback_data="cl_set_freq")],
        [InlineKeyboardButton(f"Count Stickers: {'✅' if stickers_enabled else '❌'}", callback_data="cl_toggle_stickers")],
        [InlineKeyboardButton(f"Count Commands: {'✅' if commands_enabled else '❌'}", callback_data="cl_toggle_commands")],
        [InlineKeyboardButton("Done", callback_data="cl_done")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_settings_text():
    """Gets the formatted text for the settings message."""
    settings = await get_catch_limit_settings()
    return (
        "Hiya! Let's tweak how often your lovely waifus appear! 💖\n\n"
        "These are the current global settings:"
        f"\n- **Message Frequency**: A new waifu appears every **{settings.get('frequency', 100)}** messages."
        f"\n- **Count Stickers**: **{'Yes!' if settings.get('include_stickers', False) else 'Nope!'}**"
        f"\n- **Count Commands**: **{'You bet!' if settings.get('include_commands', False) else 'Nuh-uh.'}**"
    )

# --- Command and Callback Handlers ---

async def waifu_catch_limit(update: Update, context: CallbackContext) -> None:
    """Owner command to configure waifu catch limits."""
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    text = await get_settings_text()
    keyboard = await build_settings_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
    return ConversationHandler.END

async def catch_limit_callback_handler(update: Update, context: CallbackContext) -> None:
    """Handles callbacks from the settings keyboard."""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id != OWNER_ID:
        await query.answer("This is not for you!", show_alert=True)
        return ConversationHandler.END

    action = query.data

    if action == "cl_toggle_stickers":
        current_settings = await get_catch_limit_settings()
        new_value = not current_settings.get('include_stickers', False)
        await update_catch_limit_setting('include_stickers', new_value)

    elif action == "cl_toggle_commands":
        current_settings = await get_catch_limit_settings()
        new_value = not current_settings.get('include_commands', False)
        await update_catch_limit_setting('include_commands', new_value)

    elif action == "cl_set_freq":
        await query.message.reply_text("Tell me, master! After how many messages should a new challenger appear? Give me a number! 💌")
        return SET_FREQUENCY

    elif action == "cl_done":
        await query.edit_message_text("Settings saved.")
        return ConversationHandler.END

    # Update the message with new settings
    text = await get_settings_text()
    keyboard = await build_settings_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    return ConversationHandler.END

async def set_frequency_handler(update: Update, context: CallbackContext) -> int:
    """Handles the new frequency value sent by the owner."""
    try:
        frequency = int(update.message.text)
        if frequency < 50:
            await update.message.reply_text("Frequency must be at least 50.")
            return SET_FREQUENCY

        await update_catch_limit_setting('frequency', frequency)
        await update.message.reply_text(f"Global frequency set to {frequency}.")

        # Resend the settings panel
        text = await get_settings_text()
        keyboard = await build_settings_keyboard()
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return ConversationHandler.END

    except (ValueError, TypeError):
        await update.message.reply_text("Invalid number. Please send a valid integer.")
        return SET_FREQUENCY

async def cancel_handler(update: Update, context: CallbackContext) -> int:
    """Cancels the conversation."""
    await update.message.reply_text("Action cancelled.")
    return ConversationHandler.END

# --- Add handlers to application ---
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('waifu_catch_limit', waifu_catch_limit)],
    states={
        SET_FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_frequency_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel_handler)],
    per_message=False,
    conversation_timeout=300,
)

application.add_handler(conv_handler)
application.add_handler(CallbackQueryHandler(catch_limit_callback_handler, pattern='^cl_'))
