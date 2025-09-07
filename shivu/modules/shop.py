from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, CallbackQueryHandler, MessageHandler, filters,
    ConversationHandler, CallbackContext
)

from shivu import application, OWNER_ID, bot_settings_collection
from shivu.helpers.logger import log_activity
from shivu.helpers.decorators import owner_only

# --- Constants ---
SHOP_SETTINGS_NAME = 'shop_settings'
RARITY_LIST = [
    "⚪️ Common", "🟢 Medium", "🟣 Rare", "🟡 Legendary", "❄️ Winter", "🏝️ Summer",
    "☔ Rain", "💐 Velentine", "🎄 Christmas", "🎃 Halloween", "🧬 X-Cross",
    "🐉 Unique", "🔮 Limited", "🪽 Celestial", "👑 Special"
]
# Conversation states
(
    MAIN_MENU, RARITY_MENU, SET_RARITY_AMOUNT,
) = range(3)

# --- Helper Functions ---

async def get_shop_settings():
    """Fetches shop settings from the database."""
    settings = await bot_settings_collection.find_one({'setting': SHOP_SETTINGS_NAME})
    if not settings:
        # Default settings: shop off, no rarities configured
        return {'enabled': False, 'rarities': {}}
    return settings

async def update_shop_setting(key, value):
    """Updates a top-level shop setting."""
    await bot_settings_collection.update_one(
        {'setting': SHOP_SETTINGS_NAME},
        {'$set': {key: value}},
        upsert=True
    )

async def update_rarity_in_settings(rarity_name, amount=None):
    """Updates or toggles a rarity in the shop settings."""
    settings = await get_shop_settings()
    rarities = settings.get('rarities', {})

    if amount is not None:
        # Set a specific amount
        rarities[rarity_name] = amount
    else:
        # Toggle the rarity (if it exists, remove it; if not, add with default 0)
        if rarity_name in rarities:
            del rarities[rarity_name]
        else:
            rarities[rarity_name] = 0 # Default to 0, admin must set amount

    await update_shop_setting('rarities', rarities)

# --- Keyboard Builders ---

async def build_main_menu_keyboard():
    settings = await get_shop_settings()
    shop_status = "✅ Enabled" if settings.get('enabled', False) else "❌ Disabled"
    keyboard = [
        [InlineKeyboardButton(f"Shop Status: {shop_status}", callback_data="ss_toggle_shop")],
        [InlineKeyboardButton("Configure Rarities", callback_data="ss_rarity_menu")],
        [InlineKeyboardButton("Done", callback_data="ss_done")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def build_rarity_menu_keyboard():
    settings = await get_shop_settings()
    rarities_config = settings.get('rarities', {})
    keyboard = []

    for rarity in RARITY_LIST:
        amount = rarities_config.get(rarity)
        is_enabled = amount is not None

        status_button = InlineKeyboardButton(
            f"{'✅' if is_enabled else '❌'} {rarity}",
            callback_data=f"ss_toggle_rarity:{rarity}"
        )
        amount_button = InlineKeyboardButton(
            f"Amount: {amount if is_enabled else 'N/A'}",
            callback_data=f"ss_set_amount:{rarity}"
        )
        keyboard.append([status_button, amount_button])

    keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="ss_main_menu")])
    return InlineKeyboardMarkup(keyboard)

# --- Command and State Handlers ---

@owner_only
async def shop_settings_start(update: Update, context: CallbackContext) -> int:
    """Entry point for the /shop_settings command."""
    text = "⚙️ **Shop Settings**\n\nManage the waifu shop settings from here."
    keyboard = await build_main_menu_keyboard()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
    return MAIN_MENU

async def main_menu_handler(update: Update, context: CallbackContext) -> int:
    """Handles callbacks from the main settings menu."""
    query = update.callback_query
    action = query.data

    if action == "ss_toggle_shop":
        settings = await get_shop_settings()
        await update_shop_setting('enabled', not settings.get('enabled', False))
        keyboard = await build_main_menu_keyboard()
        await query.edit_message_reply_markup(keyboard)
        return MAIN_MENU

    elif action == "ss_rarity_menu":
        text = "Configure which rarities appear in the shop and how many of each."
        keyboard = await build_rarity_menu_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        return RARITY_MENU

    elif action == "ss_done":
        await query.edit_message_text("Shop settings saved.")
        return ConversationHandler.END

async def rarity_menu_handler(update: Update, context: CallbackContext) -> int:
    """Handles callbacks from the rarity configuration menu."""
    query = update.callback_query
    action, _, value = query.data.partition(':')

    if action == "ss_toggle_rarity":
        await update_rarity_in_settings(value)
        keyboard = await build_rarity_menu_keyboard()
        await query.edit_message_reply_markup(keyboard)
        return RARITY_MENU

    elif action == "ss_set_amount":
        context.user_data['current_rarity'] = value
        await query.message.reply_text(f"Please send the number of '{value}' waifus to show in the shop.")
        return SET_RARITY_AMOUNT

    elif action == "ss_main_menu":
        return await shop_settings_start(update, context)

async def set_rarity_amount_handler(update: Update, context: CallbackContext) -> int:
    """Handles the owner's input for rarity amount."""
    try:
        amount = int(update.message.text)
        rarity_to_set = context.user_data.get('current_rarity')

        if not rarity_to_set:
            await update.message.reply_text("Something went wrong. Please try again.")
            return await shop_settings_start(update, context)

        await update_rarity_in_settings(rarity_to_set, amount)
        await update.message.reply_text(f"Set amount for '{rarity_to_set}' to {amount}.")

        del context.user_data['current_rarity']

        # Go back to rarity menu
        text = "Configure which rarities appear in the shop and how many of each."
        keyboard = await build_rarity_menu_keyboard()
        await update.message.reply_text(text, reply_markup=keyboard)
        return RARITY_MENU

    except (ValueError, TypeError):
        await update.message.reply_text("Invalid number. Please send a valid integer.")
        return SET_RARITY_AMOUNT

async def done(update: Update, context: CallbackContext) -> int:
    """Ends the conversation."""
    await update.message.reply_text("Shop settings saved.")
    return ConversationHandler.END

# --- Price Map ---
RARITY_PRICES = {
    "⚪️ Common": 100,
    "🟢 Medium": 500,
    "🟣 Rare": 1000,
    "🟡 Legendary": 5000,
    "❄️ Winter": 2000,
    "🏝️ Summer": 2000,
    "☔ Rain": 2000,
    "💐 Velentine": 3000,
    "🎄 Christmas": 3000,
    "🎃 Halloween": 3000,
    "🧬 X-Cross": 7500,
    "🐉 Unique": 10000,
    "🔮 Limited": 15000,
    "🪽 Celestial": 25000,
    "👑 Special": 50000,
}

# --- Shop Generation Job ---

async def refresh_shop_job(application):
    """The background job to refresh the shop inventory daily."""
    from shivu import collection as character_collection, shop_inventory_collection

    await log_activity(application, "🔄 Running daily shop refresh job...")

    settings = await get_shop_settings()
    if not settings.get('enabled', False):
        print("Shop is disabled, clearing inventory and skipping refresh.")
        await shop_inventory_collection.delete_many({})
        return

    await shop_inventory_collection.delete_many({})

    rarities_to_sell = settings.get('rarities', {})
    new_inventory = []

    for rarity, amount in rarities_to_sell.items():
        if amount <= 0:
            continue

        # Get random characters of the specified rarity
        pipeline = [
            {'$match': {'rarity': rarity}},
            {'$sample': {'size': amount}}
        ]
        random_characters = await character_collection.aggregate(pipeline).to_list(length=amount)

        for char in random_characters:
            price = RARITY_PRICES.get(char['rarity'], 1000) # Default price if rarity not in map
            shop_item = {
                'character_id': char['id'],
                'name': char['name'],
                'anime': char['anime'],
                'rarity': char['rarity'],
                'img_url': char['img_url'],
                'price': price,
            }
            new_inventory.append(shop_item)

    if new_inventory:
        await shop_inventory_collection.insert_many(new_inventory)

    await log_activity(application, f"✅ Shop refresh complete. Added {len(new_inventory)} items to the inventory.")


# --- User-Facing Shop Command ---

async def shop_command(update: Update, context: CallbackContext) -> None:
    """Displays the waifu shop to the user."""
    from shivu import shop_inventory_collection

    settings = await get_shop_settings()
    if not settings.get('enabled', False):
        await update.message.reply_text("Aww, my little shop is closed right now! I'm probably restocking. Please come back later! 🛍️")
        return

    inventory = await shop_inventory_collection.find().to_list(length=None)
    if not inventory:
        await update.message.reply_text("Oh no! It looks like all the waifus have been bought already! Check back after the next restock! 텅 빈")
        return

    await display_shop_item(update, context, 0)

async def display_shop_item(update: Update, context: CallbackContext, page: int):
    """Helper function to display a single shop item."""
    from shivu import shop_inventory_collection, user_collection

    inventory = await shop_inventory_collection.find().to_list(length=None)
    total_items = len(inventory)

    # Page validation
    if not (0 <= page < total_items):
        await update.callback_query.answer("Invalid item.", show_alert=True)
        return

    item = inventory[page]
    user_id = update.effective_user.id
    user = await user_collection.find_one({'id': user_id})
    wallet_balance = user.get('wallet', 0) if user else 0

    # Check if user already owns this character
    user_owns_character = False
    if user and any(c['id'] == item['character_id'] for c in user.get('characters', [])):
        user_owns_character = True

    # Build caption and keyboard
    caption = (
        f"🛍️ **Osaragi's Waifu Shop**\n\n"
        f"**Name**: {item['name']} ({item['anime']})\n"
        f"**Rarity**: {item['rarity']}\n"
        f"**Price**: {item['price']}  coins\n\n"
        f"Your Balance: {wallet_balance} coins"
    )

    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"shop_nav:{page-1}"))

    buy_text = "✅ Owned" if user_owns_character else "Buy"
    buy_button = InlineKeyboardButton(buy_text, callback_data=f"shop_buy:{page}")
    if user_owns_character:
        buy_button.disabled = True # This doesn't actually disable it, just a visual cue. Logic is handled in callback.

    nav_row.append(buy_button)

    if page < total_items - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"shop_nav:{page+1}"))

    keyboard.append(nav_row)

    from telegram import InputMediaPhoto
    # Send or edit message
    if update.callback_query:
        await update.callback_query.answer()
        media = InputMediaPhoto(media=item['img_url'], caption=caption, parse_mode='Markdown')
        await update.callback_query.edit_message_media(
            media=media,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_photo(
            photo=item['img_url'],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def shop_callback_handler(update: Update, context: CallbackContext):
    """Handles button presses from the shop."""
    query = update.callback_query
    action, _, value = query.data.partition(':')
    page = int(value)

    if action == "shop_nav":
        await display_shop_item(update, context, page)

    elif action == "shop_buy":
        from shivu import shop_inventory_collection, user_collection, collection as character_collection

        inventory = await shop_inventory_collection.find().to_list(length=None)
        if not (0 <= page < len(inventory)):
            await query.answer("This item is no longer available.", show_alert=True)
            return

        item_to_buy = inventory[page]
        user_id = query.from_user.id

        user = await user_collection.find_one({'id': user_id})
        if not user:
            await query.answer("You need to guess a character first to use the shop!", show_alert=True)
            return

        # Check ownership again to be sure
        if any(c['id'] == item_to_buy['character_id'] for c in user.get('characters', [])):
            await query.answer("Hehe, you're already the proud owner of this one! Let someone else have a chance! 😉", show_alert=True)
            return

        wallet_balance = user.get('wallet', 0)
        price = item_to_buy['price']

        if wallet_balance < price:
            await query.answer(f"Eeep! It looks like your wallet is a little light for this one, senpai! You need {price} coins, but you only have {wallet_balance}. 💔", show_alert=True)
            return

        # Fetch full character details from main collection
        character_to_add = await character_collection.find_one({'id': item_to_buy['character_id']})
        if not character_to_add:
            await query.answer("An error occurred, this character could not be found in the main database.", show_alert=True)
            return

        # Perform transaction
        await user_collection.update_one(
            {'id': user_id},
            {
                '$inc': {'wallet': -price},
                '$push': {'characters': character_to_add}
            }
        )

        await query.answer(f"Yay! 🎉 You've successfully welcomed {item_to_buy['name']} into your harem for {price} coins! Take good care of them! ❤️", show_alert=True)
        await log_activity(context.application, f"🛒 <b>Character Purchased</b>\n<b>User:</b> {query.from_user.mention_html()}\n<b>Character:</b> {item_to_buy['name']} ({item_to_buy['id']})\n<b>Price:</b> {price}")

        # Refresh the shop view to show "Owned"
        await display_shop_item(update, context, page)


# --- Add handlers to application ---
shop_settings_conv = ConversationHandler(
    entry_points=[CommandHandler('shop_settings', shop_settings_start)],
    states={
        MAIN_MENU: [CallbackQueryHandler(main_menu_handler, pattern='^ss_')],
        RARITY_MENU: [CallbackQueryHandler(rarity_menu_handler, pattern='^ss_')],
        SET_RARITY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_rarity_amount_handler)],
    },
    fallbacks=[CommandHandler('done', done)],
    per_message=False,
)

application.add_handler(shop_settings_conv)
application.add_handler(CommandHandler('shop', shop_command))
application.add_handler(CallbackQueryHandler(shop_callback_handler, pattern='^shop_'))
