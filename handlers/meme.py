import os
import random
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

MEME_FOLDER = "data/memes"

def get_memes():
    return [f for f in os.listdir(MEME_FOLDER)
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

# /meme command
async def meme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memes = get_memes()
    if not memes:
        await update.message.reply_text("❌ Koi meme image nahi mili.")
        return
    to_send = min(2, len(memes))
    selected = random.sample(memes, to_send)
    for fname in selected:
        path = os.path.join(MEME_FOLDER, fname)
        with open(path, 'rb') as f:
            await update.message.reply_photo(photo=f, caption="😂 Meme")

# Meme Button (callback_data="meme")
async def meme_button(update, context):
    query = update.callback_query
    await query.answer()
    memes = get_memes()
    if not memes:
        await query.edit_message_text("❌ Koi meme image nahi mili.")
        return
    fname = random.choice(memes)
    path = os.path.join(MEME_FOLDER, fname)
    with open(path, 'rb') as f:
        await query.message.reply_photo(photo=f, caption="😂 Meme")

# Job queue: Daily meme
async def send_daily_meme(context):
    chat_id = context.job.data["chat_id"]
    memes = get_memes()
    if not memes:
        return
    fname = random.choice(memes)
    path = os.path.join(MEME_FOLDER, fname)
    with open(path, 'rb') as f:
        await context.bot.send_photo(chat_id=chat_id, photo=f, caption="😂 Daily Meme")

meme_handler = CommandHandler('meme', meme_command)
meme_button_handler = CallbackQueryHandler(meme_button, pattern="^meme$")
