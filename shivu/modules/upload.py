import urllib.request
from pymongo import ReturnDocument
import aiohttp

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from shivu import application, sudo_users, collection, db, CHARA_CHANNEL_ID, SUPPORT_CHAT, CATBOX_USER_HASH
from shivu.helpers.logger import log_activity

WRONG_FORMAT_TEXT = """Wrong ❌️ format...  Reply to an image with:
/upload character-name anime-name rarity-number

use rarity number accordingly rarity Map

1.  ⚪️ Common
2.  🟢 Medium
3.  🟣 Rare
4.  🟡 Legendary
5.  ❄️ Winter
6.  🏝️ Summer
7.  ☔ Rain
8.  💐 Velentine
9.  🎄 Christmas
10. 🎃 Halloween
11. 🧬 X-Cross
12. 🐉 Unique
13. 🔮 Limited
14. 🪽 Celestial
15. 👑 Special
"""



async def get_next_sequence_number(sequence_name):
    sequence_collection = db.sequences
    sequence_document = await sequence_collection.find_one_and_update(
        {'_id': sequence_name}, 
        {'$inc': {'sequence_value': 1}}, 
        return_document=ReturnDocument.AFTER
    )
    if not sequence_document:
        await sequence_collection.insert_one({'_id': sequence_name, 'sequence_value': 0})
        return 0
    return sequence_document['sequence_value']

async def upload_to_catbox(file_bytearray: bytearray) -> str:
    """Uploads a file to Catbox.moe and returns the URL."""
    url = "https://catbox.moe/user/api.php"
    form_data = aiohttp.FormData()
    form_data.add_field("reqtype", "fileupload")
    form_data.add_field("userhash", CATBOX_USER_HASH)
    form_data.add_field("fileToUpload", file_bytearray, filename="image.png", content_type="image/png")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form_data) as response:
            if response.status == 200:
                return await response.text()
            else:
                error_text = await response.text()
                raise Exception(f"Catbox API Error: {response.status} - {error_text}")

async def upload(update: Update, context: CallbackContext) -> None:
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('Ask My Owner...')
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text(WRONG_FORMAT_TEXT)
        return

    try:
        args = context.args
        if len(args) != 3:
            await update.message.reply_text(WRONG_FORMAT_TEXT)
            return

        character_name = args[0].replace('-', ' ').title()
        anime = args[1].replace('-', ' ').title()

        rarity_map = {
            1: "⚪️ Common", 2: "🟢 Medium", 3: "🟣 Rare", 4: "🟡 Legendary",
            5: "❄️ Winter", 6: "🏝️ Summer", 7: "☔ Rain", 8: "💐 Velentine",
            9: "🎄 Christmas", 10: "🎃 Halloween", 11: "🧬 X-Cross", 12: "🐉 Unique",
            13: "🔮 Limited", 14: "🪽 Celestial", 15: "👑 Special"
        }
        try:
            rarity = rarity_map[int(args[2])]
        except (KeyError, ValueError):
            await update.message.reply_text('Invalid rarity. Please use a number between 1 and 15.')
            return

        # Download the image
        photo = update.message.reply_to_message.photo[-1]
        file = await photo.get_file()
        file_bytearray = await file.download_as_bytearray()

        # Upload to Catbox
        progress_message = await update.message.reply_text("Uploading image to Catbox...")
        try:
            image_url = await upload_to_catbox(file_bytearray)
        except Exception as e:
            await progress_message.edit_text(f"Failed to upload to Catbox. Error: {e}")
            return

        await progress_message.edit_text("Image uploaded successfully! Adding character to database...")

        id = str(await get_next_sequence_number('character_id')).zfill(2)
        character = {
            'img_url': image_url,
            'name': character_name,
            'anime': anime,
            'rarity': rarity,
            'id': id
        }

        try:
            message = await context.bot.send_photo(
                chat_id=CHARA_CHANNEL_ID,
                photo=image_url,
                caption=f'<b>Character Name:</b> {character_name}\n<b>Anime Name:</b> {anime}\n<b>Rarity:</b> {rarity}\n<b>ID:</b> {id}\nAdded by <a href="tg://user?id={update.effective_user.id}">{update.effective_user.first_name}</a>',
                parse_mode='HTML'
            )
            character['message_id'] = message.message_id
            await collection.insert_one(character)
            await progress_message.edit_text('CHARACTER ADDED....')
            await log_activity(context.application, f"➕ <b>New Character</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>Name:</b> {character_name}\n<b>Anime:</b> {anime}\n<b>Rarity:</b> {rarity}\n<b>ID:</b> {id}")
        except Exception as e:
            await collection.insert_one(character)
            await progress_message.edit_text(f"Character Added but failed to send to channel. Error: {e}")
            await log_activity(context.application, f"➕ <b>New Character (No Channel)</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>Name:</b> {character_name}\n<b>Anime:</b> {anime}\n<b>Rarity:</b> {rarity}\n<b>ID:</b> {id}")
        
    except Exception as e:
        await update.message.reply_text(f'Character Upload Unsuccessful. Error: {str(e)}\nIf you think this is a source error, forward to: {SUPPORT_CHAT}')

async def delete(update: Update, context: CallbackContext) -> None:
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('Ask my Owner to use this Command...')
        return

    try:
        args = context.args
        if len(args) != 1:
            await update.message.reply_text('Incorrect format... Please use: /delete ID')
            return

        
        character = await collection.find_one_and_delete({'id': args[0]})

        if character:
            
            await context.bot.delete_message(chat_id=CHARA_CHANNEL_ID, message_id=character['message_id'])
            await update.message.reply_text('DONE')
        else:
            await update.message.reply_text('Deleted Successfully from db, but character not found In Channel')
    except Exception as e:
        await update.message.reply_text(f'{str(e)}')

async def update(update: Update, context: CallbackContext) -> None:
    if str(update.effective_user.id) not in sudo_users:
        await update.message.reply_text('You do not have permission to use this command.')
        return

    try:
        args = context.args
        if len(args) != 3:
            await update.message.reply_text('Incorrect format. Please use: /update id field new_value')
            return

        # Get character by ID
        character = await collection.find_one({'id': args[0]})
        if not character:
            await update.message.reply_text('Character not found.')
            return

        # Check if field is valid
        valid_fields = ['img_url', 'name', 'anime', 'rarity']
        if args[1] not in valid_fields:
            await update.message.reply_text(f'Invalid field. Please use one of the following: {", ".join(valid_fields)}')
            return

        # Update field
        field_to_update = args[1].lower()

        if field_to_update == 'img_url':
            if not update.message.reply_to_message or not update.message.reply_to_message.photo:
                await update.message.reply_text("You must reply to an image to update the img_url.")
                return

            photo = update.message.reply_to_message.photo[-1]
            file = await photo.get_file()
            file_bytearray = await file.download_as_bytearray()

            progress_message = await update.message.reply_text("Uploading new image to Catbox...")
            try:
                new_value = await upload_to_catbox(file_bytearray)
                await progress_message.edit_text("Image uploaded, updating database...")
            except Exception as e:
                await progress_message.edit_text(f"Failed to upload to Catbox. Error: {e}")
                return
        else:
            if len(args) != 3:
                await update.message.reply_text('Incorrect format. Please use: /update id field new_value')
                return

            if field_to_update in ['name', 'anime']:
                new_value = args[2].replace('-', ' ').title()
            elif field_to_update == 'rarity':
                rarity_map = {
                    1: "⚪️ Common", 2: "🟢 Medium", 3: "🟣 Rare", 4: "🟡 Legendary",
                    5: "❄️ Winter", 6: "🏝️ Summer", 7: "☔ Rain", 8: "💐 Velentine",
                    9: "🎄 Christmas", 10: "🎃 Halloween", 11: "🧬 X-Cross", 12: "🐉 Unique",
                    13: "🔮 Limited", 14: "🪽 Celestial", 15: "👑 Special"
                }
                try:
                    new_value = rarity_map[int(args[2])]
                except (KeyError, ValueError):
                    await update.message.reply_text('Invalid rarity. Please use a number between 1 and 15.')
                    return
            else:
                await update.message.reply_text(f'Invalid field. Please use one of the following: {", ".join(valid_fields)}')
                return

        # Update the database
        await collection.find_one_and_update({'id': args[0]}, {'$set': {field_to_update: new_value}})

        # Fetch the updated character document for the caption
        updated_character = await collection.find_one({'id': args[0]})

        # Update the message in the character channel
        try:
            if field_to_update == 'img_url':
                # Delete the old message and send a new one with the new photo
                if 'message_id' in character:
                    await context.bot.delete_message(chat_id=CHARA_CHANNEL_ID, message_id=character['message_id'])

                message = await context.bot.send_photo(
                    chat_id=CHARA_CHANNEL_ID,
                    photo=new_value,
                    caption=f'<b>Character Name:</b> {updated_character["name"]}\n<b>Anime Name:</b> {updated_character["anime"]}\n<b>Rarity:</b> {updated_character["rarity"]}\n<b>ID:</b> {updated_character["id"]}\nUpdated by <a href="tg://user?id={update.effective_user.id}">{update.effective_user.first_name}</a>',
                    parse_mode='HTML'
                )
                await collection.find_one_and_update({'id': args[0]}, {'$set': {'message_id': message.message_id}})
            else:
                # Edit the caption of the existing message
                if 'message_id' in character:
                    await context.bot.edit_message_caption(
                        chat_id=CHARA_CHANNEL_ID,
                        message_id=character['message_id'],
                        caption=f'<b>Character Name:</b> {updated_character["name"]}\n<b>Anime Name:</b> {updated_character["anime"]}\n<b>Rarity:</b> {updated_character["rarity"]}\n<b>ID:</b> {updated_character["id"]}\nUpdated by <a href="tg://user?id={update.effective_user.id}">{update.effective_user.first_name}</a>',
                        parse_mode='HTML'
                    )
        except Exception as e:
            await update.message.reply_text(f"Database updated, but failed to update channel message. Error: {e}")

        await update.message.reply_text('✅ Update successful.')
        await log_activity(context.application, f"✏️ <b>Character Updated</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>ID:</b> {args[0]}\n<b>Field:</b> {field_to_update}")
    except Exception as e:
        await update.message.reply_text(f'I guess did not added bot in channel.. or character uploaded Long time ago.. Or character not exits.. orr Wrong id')

UPLOAD_HANDLER = CommandHandler('upload', upload, block=False)
application.add_handler(UPLOAD_HANDLER)
DELETE_HANDLER = CommandHandler('delete', delete, block=False)
application.add_handler(DELETE_HANDLER)
UPDATE_HANDLER = CommandHandler('update', update, block=False)
application.add_handler(UPDATE_HANDLER)
