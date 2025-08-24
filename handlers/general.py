from telegram.ext import CommandHandler
from utils.fileops import get_message, alert_admin

# /help command
async def help_command(update, context):
    msg = get_message("help")
    await update.message.reply_text(msg)

# /about command
async def about_command(update, context):
    msg = get_message("about")
    await update.message.reply_text(msg)

# /alert command
async def alert_command(update, context):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("⚠️ Kripya apna problem likhe: /alert <aapki problem>")
        return
    
    problem_text = " ".join(context.args)
    await alert_admin(context, user.username or "Unknown", problem_text)
    await update.message.reply_text("✅ Aapka alert admin ko bhej diya gaya hai.")

# Handlers
help_handler = CommandHandler("help", help_command)
about_handler = CommandHandler("about", about_command)
alert_handler = CommandHandler("alert", alert_command)
