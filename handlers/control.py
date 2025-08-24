from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import os

# --- STOPBOT ---
async def stopbot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in context.application.bot_data.get("admin_ids", []):
        await update.message.reply_text("❌ Only admins can stop the bot.")
        return

    open("bot_stop.lock", "w").close()
    await update.message.reply_text("🛑 Stop signal sent. Bot will stop shortly.")

# --- RESTARTBOT ---
async def restartbot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in context.application.bot_data.get("admin_ids", []):
        await update.message.reply_text("❌ Only admins can restart the bot.")
        return

    if os.path.exists("bot_stop.lock"):
        os.remove("bot_stop.lock")
        await update.message.reply_text("▶️ Restart signal sent. Bot will start again soon.")
    else:
        await update.message.reply_text("Bot is already running.")
