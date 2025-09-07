import importlib
import time
import random
import re
import asyncio
from html import escape 

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, filters, TypeHandler
from telegram.ext.dispatcher import ApplicationHandlerStop

from shivu import collection, top_global_groups_collection, group_user_totals_collection, user_collection, user_totals_collection, shivuu
from shivu import (
    application, SUPPORT_CHAT, UPDATE_CHAT, db, LOGGER, OWNER_ID, sudo_users,
    banned_users_collection, banned_groups_collection,
    frozen_users_collection, frozen_groups_collection
)
from shivu.modules import ALL_MODULES
from shivu.modules.maintenance import get_maintenance_status, DEFAULT_MAINTENANCE_MESSAGE
from shivu.modules.catch_limit import get_catch_limit_settings


locks = {}
message_counters = {}
spam_counters = {}
last_characters = {}
sent_characters = {}
first_correct_guesses = {}
message_counts = {}


for module_name in ALL_MODULES:
    imported_module = importlib.import_module("shivu.modules." + module_name)


last_user = {}
warned_users = {}
def escape_markdown(text):
    escape_chars = r'\*_`\\~>#+-=|{}.!'
    return re.sub(r'([%s])' % re.escape(escape_chars), r'\\\1', text)


async def message_counter(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return

    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id

    # Get global catch limit settings
    catch_limit_settings = await get_catch_limit_settings()

    # Check if stickers should be counted
    if update.message.sticker and not catch_limit_settings.get('include_stickers', False):
        return

    # Check if commands should be counted
    if update.message.text and update.message.text.startswith('/') and not catch_limit_settings.get('include_commands', False):
        return

    if chat_id not in locks:
        locks[chat_id] = asyncio.Lock()
    lock = locks[chat_id]

    async with lock:
        # Get global frequency and then check for chat-specific override
        message_frequency = catch_limit_settings.get('frequency', 100)
        chat_specific_frequency = await user_totals_collection.find_one({'chat_id': chat_id})
        if chat_specific_frequency and 'message_frequency' in chat_specific_frequency:
            message_frequency = chat_specific_frequency['message_frequency']
        
        # Anti-spam logic
        if chat_id in last_user and last_user[chat_id]['user_id'] == user_id:
            last_user[chat_id]['count'] += 1
            if last_user[chat_id]['count'] >= 10:
                if user_id in warned_users and time.time() - warned_users[user_id] < 600:
                    return
                else:
                    await update.message.reply_text(f"⚠️ Don't Spam {update.effective_user.first_name}...\nYour Messages Will be ignored for 10 Minutes...")
                    warned_users[user_id] = time.time()
                    return
        else:
            last_user[chat_id] = {'user_id': user_id, 'count': 1}

        # Increment message count
        if chat_id in message_counts:
            message_counts[chat_id] += 1
        else:
            message_counts[chat_id] = 1

        # Check if it's time to send a character
        if message_counts[chat_id] % message_frequency == 0:
            await send_image(update, context)
            message_counts[chat_id] = 0
            
async def send_image(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id

    all_characters = list(await collection.find({}).to_list(length=None))
    
    if chat_id not in sent_characters:
        sent_characters[chat_id] = []

    if len(sent_characters[chat_id]) == len(all_characters):
        sent_characters[chat_id] = []

    character = random.choice([c for c in all_characters if c['id'] not in sent_characters[chat_id]])

    sent_characters[chat_id].append(character['id'])
    last_characters[chat_id] = character

    if chat_id in first_correct_guesses:
        del first_correct_guesses[chat_id]

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=character['img_url'],
        caption=f"""A New {character['rarity']} Character Appeared...\n/guess Character Name and add in Your Harem""",
        parse_mode='Markdown')


async def guess(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id not in last_characters:
        return

    if chat_id in first_correct_guesses:
        await update.message.reply_text(f'❌️ Already Guessed By Someone.. Try Next Time Bruhh ')
        return

    guess = ' '.join(context.args).lower() if context.args else ''
    
    if "()" in guess or "&" in guess.lower():
        await update.message.reply_text("Nahh You Can't use This Types of words in your guess..❌️")
        return


    name_parts = last_characters[chat_id]['name'].lower().split()

    if sorted(name_parts) == sorted(guess.split()) or any(part == guess for part in name_parts):

    
        first_correct_guesses[chat_id] = user_id
        
        user = await user_collection.find_one({'id': user_id})
        if user:
            update_fields = {'$push': {'characters': last_characters[chat_id]}}

            # Initialize wallet if it doesn't exist
            if 'wallet' not in user:
                update_fields['$set'] = {'wallet': 0}

            if hasattr(update.effective_user, 'username') and update.effective_user.username != user.get('username'):
                if '$set' not in update_fields: update_fields['$set'] = {}
                update_fields['$set']['username'] = update.effective_user.username
            if update.effective_user.first_name != user.get('first_name'):
                if '$set' not in update_fields: update_fields['$set'] = {}
                update_fields['$set']['first_name'] = update.effective_user.first_name

            await user_collection.update_one({'id': user_id}, update_fields)
      
        elif hasattr(update.effective_user, 'username'):
            await user_collection.insert_one({
                'id': user_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'characters': [last_characters[chat_id]],
                'wallet': 0  # Initialize wallet for new users
            })

        
        group_user_total = await group_user_totals_collection.find_one({'user_id': user_id, 'group_id': chat_id})
        if group_user_total:
            update_fields = {}
            if hasattr(update.effective_user, 'username') and update.effective_user.username != group_user_total.get('username'):
                update_fields['username'] = update.effective_user.username
            if update.effective_user.first_name != group_user_total.get('first_name'):
                update_fields['first_name'] = update.effective_user.first_name
            if update_fields:
                await group_user_totals_collection.update_one({'user_id': user_id, 'group_id': chat_id}, {'$set': update_fields})
            
            await group_user_totals_collection.update_one({'user_id': user_id, 'group_id': chat_id}, {'$inc': {'count': 1}})
      
        else:
            await group_user_totals_collection.insert_one({
                'user_id': user_id,
                'group_id': chat_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'count': 1,
            })


    
        group_info = await top_global_groups_collection.find_one({'group_id': chat_id})
        if group_info:
            update_fields = {}
            if update.effective_chat.title != group_info.get('group_name'):
                update_fields['group_name'] = update.effective_chat.title
            if update_fields:
                await top_global_groups_collection.update_one({'group_id': chat_id}, {'$set': update_fields})
            
            await top_global_groups_collection.update_one({'group_id': chat_id}, {'$inc': {'count': 1}})
      
        else:
            await top_global_groups_collection.insert_one({
                'group_id': chat_id,
                'group_name': update.effective_chat.title,
                'count': 1,
            })


        
        keyboard = [[InlineKeyboardButton(f"See Harem", switch_inline_query_current_chat=f"collection.{user_id}")]]


        await update.message.reply_text(f'<b><a href="tg://user?id={user_id}">{escape(update.effective_user.first_name)}</a></b>💖 ʏᴏᴜʀ ᴘʀᴏᴘᴏsᴀʟ ᴡᴀs ᴀᴄᴄᴇᴘᴛᴇᴅ 🎉 \n\n 💍 ʏᴏᴜ ʜᴀᴠᴇ ᴀᴅᴅᴇᴅ \n\n 🌺𝗡𝗔𝗠𝗘: <b>{last_characters[chat_id]["name"]}</b> \n𝗔𝗡𝗜𝗠𝗘: <b>{last_characters[chat_id]["anime"]}</b> \n🐉𝙍𝘼𝙍𝙄𝙏𝙔: <b>{last_characters[chat_id]["rarity"]}</b>\n\nᴛᴏ ʏᴏᴜʀ ʜᴀʀᴇᴍ 💎 \n\n💡 ᴄʜᴇᴄᴋ ɪᴛ ᴜsɪɴɢ /ᴍʏʜᴀʀᴇᴍ', parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    else:
        await update.message.reply_text('Please Write Correct Character Name... ❌️')
   

async def fav(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id

    
    if not context.args:
        await update.message.reply_text('Please provide Character id...')
        return

    character_id = context.args[0]

    
    user = await user_collection.find_one({'id': user_id})
    if not user:
        await update.message.reply_text('You have not Guessed any characters yet....')
        return


    character = next((c for c in user['characters'] if c['id'] == character_id), None)
    if not character:
        await update.message.reply_text('This Character is Not In your collection')
        return

    
    user['favorites'] = [character_id]

    
    await user_collection.update_one({'id': user_id}, {'$set': {'favorites': user['favorites']}})

    await update.message.reply_text(f'Character {character["name"]} has been added to your favorite...')
    



async def pre_update_checks(update: Update, context: CallbackContext) -> None:
    """
    Performs pre-update checks for maintenance, bans, and freezes.
    Stops handlers if any checks fail.
    """
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else 0

    # --- Ban and Freeze Checks ---
    # These checks apply to everyone, including owners, to prevent accidental usage from a banned account.

    # Check if user is banned
    if await banned_users_collection.find_one({'user_id': user_id}):
        raise ApplicationHandlerStop

    # Check if group is banned
    if chat_id and await banned_groups_collection.find_one({'group_id': chat_id}):
        try:
            await context.bot.leave_chat(chat_id)
        except:
            pass
        raise ApplicationHandlerStop

    # --- Maintenance and Freeze Checks for Non-Admins ---
    if str(user_id) == OWNER_ID or str(user_id) in sudo_users:
        return

    # Maintenance Mode Check
    maintenance_status = await get_maintenance_status()
    if maintenance_status and maintenance_status.get('enabled', False):
        message = maintenance_status.get('message', DEFAULT_MAINTENANCE_MESSAGE)
        if update.message:
            await update.message.reply_text(message)
        elif update.callback_query:
            await update.callback_query.answer(message, show_alert=True)
        raise ApplicationHandlerStop

    # Frozen User Check
    if await frozen_users_collection.find_one({'user_id': user_id}):
        if update.message:
            await update.message.reply_text("❄️ Your account has been frozen. You cannot use the bot.")
        elif update.callback_query:
            await update.callback_query.answer("❄️ Your account has been frozen.", show_alert=True)
        raise ApplicationHandlerStop

    # Frozen Group Check
    if chat_id and await frozen_groups_collection.find_one({'group_id': chat_id}):
        if update.message:
            await update.message.reply_text("❄️ This group has been frozen. The bot's services are temporarily disabled here.")
        elif update.callback_query:
            await update.callback_query.answer("❄️ This group has been frozen.", show_alert=True)
        raise ApplicationHandlerStop


from apscheduler.schedulers.asyncio import AsyncIOScheduler
from shivu.modules.shop import refresh_shop_job

def main() -> None:
    """Run bot."""

    application.add_handler(TypeHandler(Update, pre_update_checks), group=-1)

    application.add_handler(CommandHandler("fav", fav, block=False))
    application.add_handler(CommandHandler(["guess", "protecc", "collect", "grab", "marry"], guess, block=False))
    application.add_handler(CommandHandler("xfav", fav, block=False))
    application.add_handler(MessageHandler(filters.ALL, message_counter, block=False))

    application.run_polling(drop_pending_updates=True)
    
if __name__ == "__main__":
    shivuu.start()
    LOGGER.info("Bot started")

    # Start the scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh_shop_job, 'interval', hours=24, args=[application])
    scheduler.start()

    # Run the job once at startup
    asyncio.get_event_loop().run_until_complete(refresh_shop_job(application))

    main()

