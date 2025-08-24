from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler
from utils.fileops import get_message

async def start(update, context):
    user = update.effective_user
    username = user.username or user.first_name or "User"
    msg = get_message('welcome', username=username)
    keyboard = [
        [InlineKeyboardButton("📚 Topic", callback_data='topics')],
        [InlineKeyboardButton("🔎 Search", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("😄 Meme", callback_data="meme")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, reply_markup=reply_markup)

start_handler = CommandHandler('start', start)
