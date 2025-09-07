from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from shivu import (
    application, OWNER_ID,
    user_collection, group_user_totals_collection, user_totals_collection,
    banned_users_collection, banned_groups_collection,
    frozen_users_collection, frozen_groups_collection
)
from shivu.helpers.logger import log_activity
from shivu.helpers.decorators import owner_only

# --- Helper Functions ---

async def get_user_id_from_args(args):
    """Extracts a user ID from command arguments."""
    if not args:
        return None, "Please provide a user ID."
    try:
        return int(args[0]), None
    except ValueError:
        return None, "Invalid user ID provided."

# --- User Management Commands ---

@owner_only
async def ban_user(update: Update, context: CallbackContext) -> None:
    """Bans a user, deleting all their data."""
    user_id, error_message = await get_user_id_from_args(context.args)
    if error_message:
        await update.message.reply_text(error_message)
        return

    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided."

    # Check if already banned
    if await banned_users_collection.find_one({'user_id': user_id}):
        await update.message.reply_text(f"User `{user_id}` is already banned.")
        return

    # Delete user data
    await user_collection.delete_one({'id': user_id})
    await group_user_totals_collection.delete_many({'user_id': user_id})
    await user_totals_collection.delete_many({'user_id': user_id})

    # Add to banned list
    await banned_users_collection.insert_one({'user_id': user_id, 'reason': reason})

    await update.message.reply_text(f"✅ User `{user_id}` has been banned and all their data has been deleted.")
    await log_activity(context.application, f"🚫 <b>User Banned</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>User:</b> {user_id}\n<b>Reason:</b> {reason}")

@owner_only
async def unban_user(update: Update, context: CallbackContext) -> None:
    """Unbans a user."""
    user_id, error_message = await get_user_id_from_args(context.args)
    if error_message:
        await update.message.reply_text(error_message)
        return

    result = await banned_users_collection.delete_one({'user_id': user_id})
    if result.deleted_count > 0:
        await update.message.reply_text(f"✅ User `{user_id}` has been unbanned.")
        await log_activity(context.application, f"🔓 <b>User Unbanned</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>User:</b> {user_id}")
    else:
        await update.message.reply_text(f"User `{user_id}` was not found in the banned list.")

@owner_only
async def freeze_user(update: Update, context: CallbackContext) -> None:
    """Freezes a user's account."""
    user_id, error_message = await get_user_id_from_args(context.args)
    if error_message:
        await update.message.reply_text(error_message)
        return

    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided."

    await frozen_users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'reason': reason}},
        upsert=True
    )
    await update.message.reply_text(f"✅ User `{user_id}`'s account has been frozen.")
    await log_activity(context.application, f"❄️ <b>User Frozen</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>User:</b> {user_id}\n<b>Reason:</b> {reason}")

@owner_only
async def unfreeze_user(update: Update, context: CallbackContext) -> None:
    """Unfreezes a user's account."""
    user_id, error_message = await get_user_id_from_args(context.args)
    if error_message:
        await update.message.reply_text(error_message)
        return

    result = await frozen_users_collection.delete_one({'user_id': user_id})
    if result.deleted_count > 0:
        await update.message.reply_text(f"✅ User `{user_id}`'s account has been unfrozen.")
        await log_activity(context.application, f"🔥 <b>User Unfrozen</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>User:</b> {user_id}")
    else:
        await update.message.reply_text(f"User `{user_id}` was not found in the frozen list.")

# --- Group Management Commands ---

async def get_group_id_from_args(args):
    """Extracts a group ID from command arguments."""
    if not args:
        return None, "Please provide a group ID."
    try:
        # Group IDs are negative integers
        return int(args[0]), None
    except ValueError:
        return None, "Invalid group ID provided. Make sure it's a number."

@owner_only
async def ban_group(update: Update, context: CallbackContext) -> None:
    """Bans a group and makes the bot leave."""
    group_id, error_message = await get_group_id_from_args(context.args)
    if error_message:
        await update.message.reply_text(error_message)
        return

    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided."

    if await banned_groups_collection.find_one({'group_id': group_id}):
        await update.message.reply_text(f"Group `{group_id}` is already banned.")
        return

    await banned_groups_collection.insert_one({'group_id': group_id, 'reason': reason})

    try:
        await context.bot.leave_chat(group_id)
        await update.message.reply_text(f"✅ Group `{group_id}` has been banned and I have left the group.")
    except Exception as e:
        await update.message.reply_text(f"✅ Group `{group_id}` has been banned, but I failed to leave. Maybe I'm not in that group or was already kicked. Error: {e}")
    await log_activity(context.application, f"🚫 <b>Group Banned</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>Group:</b> {group_id}\n<b>Reason:</b> {reason}")

@owner_only
async def unban_group(update: Update, context: CallbackContext) -> None:
    """Unbans a group."""
    group_id, error_message = await get_group_id_from_args(context.args)
    if error_message:
        await update.message.reply_text(error_message)
        return

    result = await banned_groups_collection.delete_one({'group_id': group_id})
    if result.deleted_count > 0:
        await update.message.reply_text(f"✅ Group `{group_id}` has been unbanned.")
        await log_activity(context.application, f"🔓 <b>Group Unbanned</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>Group:</b> {group_id}")
    else:
        await update.message.reply_text(f"Group `{group_id}` was not found in the banned list.")

@owner_only
async def freeze_group(update: Update, context: CallbackContext) -> None:
    """Freezes a group."""
    group_id, error_message = await get_group_id_from_args(context.args)
    if error_message:
        await update.message.reply_text(error_message)
        return

    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided."

    await frozen_groups_collection.update_one(
        {'group_id': group_id},
        {'$set': {'reason': reason}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Group `{group_id}` has been frozen.")
    await log_activity(context.application, f"❄️ <b>Group Frozen</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>Group:</b> {group_id}\n<b>Reason:</b> {reason}")

@owner_only
async def unfreeze_group(update: Update, context: CallbackContext) -> None:
    """Unfreezes a group."""
    group_id, error_message = await get_group_id_from_args(context.args)
    if error_message:
        await update.message.reply_text(error_message)
        return

    result = await frozen_groups_collection.delete_one({'group_id': group_id})
    if result.deleted_count > 0:
        await update.message.reply_text(f"✅ Group `{group_id}` has been unfrozen.")
        await log_activity(context.application, f"🔥 <b>Group Unfrozen</b>\n<b>Admin:</b> {update.effective_user.mention_html()}\n<b>Group:</b> {group_id}")
    else:
        await update.message.reply_text(f"Group `{group_id}` was not found in the frozen list.")

# --- Add handlers to application ---
application.add_handler(CommandHandler('ban_user', ban_user, block=False))
application.add_handler(CommandHandler('unban_user', unban_user, block=False))
application.add_handler(CommandHandler('freeze_user', freeze_user, block=False))
application.add_handler(CommandHandler('unfreeze_user', unfreeze_user, block=False))

application.add_handler(CommandHandler('ban_group', ban_group, block=False))
application.add_handler(CommandHandler('unban_group', unban_group, block=False))
application.add_handler(CommandHandler('freeze_group', freeze_group, block=False))
application.add_handler(CommandHandler('unfreeze_group', unfreeze_group, block=False))
