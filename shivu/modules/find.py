import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler

from shivu import application, user_collection

RESULTS_PER_PAGE = 10

async def find_waifu(update: Update, context: CallbackContext) -> None:
    """Finds all owners of a specific waifu."""
    if not context.args:
        await update.message.reply_text("Please provide a character name to find. Usage: /find <character_name>")
        return

    character_name = " ".join(context.args)

    # Using a case-insensitive regex for a more flexible search
    query = {'characters.name': {'$regex': f'^{re.escape(character_name)}$', '$options': 'i'}}

    # Find all users who own the character
    owners = await user_collection.find(query).to_list(length=None)

    if not owners:
        await update.message.reply_text(f"Hmm, it seems '{character_name}' is still waiting for their first owner! Maybe it could be you? 🤔")
        return

    context.user_data['find_results'] = owners
    context.user_data['find_character_name'] = character_name

    await display_find_results(update, context, page=0)

async def display_find_results(update: Update, context: CallbackContext, page: int):
    """Displays a paginated list of waifu owners."""
    owners = context.user_data.get('find_results', [])
    character_name = context.user_data.get('find_character_name', 'Unknown')

    if not owners:
        await update.message.reply_text("No results found or results have expired.")
        return

    total_owners = len(owners)
    total_pages = (total_owners + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE

    start_index = page * RESULTS_PER_PAGE
    end_index = start_index + RESULTS_PER_PAGE
    current_owners = owners[start_index:end_index]

    message_text = f"🔎 Owners of **{character_name}** (Page {page + 1}/{total_pages}):\n\n"

    for user_doc in current_owners:
        user_id = user_doc['id']
        first_name = user_doc.get('first_name', 'Unknown User')

        # Count how many of that specific character the user owns
        count = sum(1 for char in user_doc.get('characters', []) if char.get('name', '').lower() == character_name.lower())

        message_text += f"- <a href='tg://user?id={user_id}'>{first_name}</a> (Owns ×{count})\n"

    keyboard = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"find_nav:{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"find_nav:{page+1}"))

    if nav_row:
        keyboard.append(nav_row)

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='HTML')

async def find_callback_handler(update: Update, context: CallbackContext) -> None:
    """Handles pagination for the find command."""
    query = update.callback_query
    _, page_str = query.data.split(':')

    await display_find_results(update, context, page=int(page_str))

application.add_handler(CommandHandler('find', find_waifu))
application.add_handler(CallbackQueryHandler(find_callback_handler, pattern='^find_nav:'))
