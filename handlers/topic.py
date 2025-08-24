import os
from io import BytesIO
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler
from utils.fileops import get_topics, get_topic_files, alert_admin
from handlers.warn import check_ban_and_block

# Base data folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "reference")

# /topic command
async def topic_command(update, context):
    topics = get_topics()
    if not topics:
        await update.message.reply_text("❌ Koi topic available nahi hai.")
        return

    keyboard = [[InlineKeyboardButton(t, callback_data=f"topic|{t.strip()}")] for t in topics]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('📂 Topics:', reply_markup=reply_markup)


# Callback query handler
async def button_handler(update, context):
    query = update.callback_query
    user = query.from_user

    # ✅ Step 1: Acknowledge callback immediately
    await query.answer()

    # ✅ Step 2: Send temporary "Please wait..." message
    waiting_msg = await query.message.reply_text("⏳ Please wait, processing...")

    try:
        # ✅ Step 3: Check ban/block
        if await check_ban_and_block(query, user):
            await waiting_msg.delete()
            return

        data = query.data.strip()

        # --- Show all topics ---
        if data == 'topics':
            topics = get_topics()
            if not topics:
                await query.edit_message_text("❌ Koi topic available nahi hai.")
                return

            keyboard = [[InlineKeyboardButton(t, callback_data=f"topic|{t.strip()}")] for t in topics]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text('@ILMsourceBot\n📂 Topics:', reply_markup=reply_markup)

        # --- Show files under selected topic ---
        elif data.startswith('topic|'):
            topic = data.split("|", 1)[1].strip()
            files = get_topic_files(topic)

            if not files:
                await query.edit_message_text(f"@ILMsourceBot\n❌ Is topic me koi content nahi mila.")
                return

            keyboard = [[InlineKeyboardButton(f, callback_data=f"file|{topic}|{f.strip()}")] for f in files]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"@ILMsourceBot\n📑 {topic} ke liye content choose karein:", reply_markup=reply_markup)

        # --- Handle file sending ---
        elif data.startswith('file|'):
            try:
                _, topic, filename = data.split("|", 2)
                topic, filename = topic.strip(), filename.strip()
                local_path = os.path.join(DATA_DIR, topic, filename)

                if not os.path.exists(local_path):
                    await query.edit_message_text(f"@ILMsourceBot\n❌ File nahi mili (server par).\n\nDEBUG: {local_path}")
                    return

                # Text files
                if filename.endswith('.txt'):
                    with open(local_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                    await query.edit_message_text(f"@ILMsourceBot\n📄 {filename}:\n\n{text[:4000]}")

                # PDFs / Images
                elif filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                    with open(local_path, 'rb') as f:
                        file_bytes = BytesIO(f.read())
                    file_bytes.name = filename

                    if filename.endswith('.pdf'):
                        await query.message.reply_document(
                            document=file_bytes,
                            caption=f"@ILMsourceBot\n📕 {filename}"
                        )
                    else:
                        await query.message.reply_photo(
                            photo=file_bytes,
                            caption=f"@ILMsourceBot\n🖼 {filename}"
                        )
                else:
                    await query.edit_message_text(f"@ILMsourceBot\n⚠️ Ye file type supported nahi hai.")

            except Exception as e:
                await alert_admin(context, user.username or "Unknown", f"File bhejne me error: {str(e)}")
                await query.edit_message_text(f"@ILMsourceBot\n⚠️ File bhejne me error. Admin ko inform kar diya gaya hai.")

    finally:
        # ✅ Step 4: Delete the temporary "Please wait..." message
        await waiting_msg.delete()


# Handlers
topic_handler = CallbackQueryHandler(
    button_handler,
    pattern=r"^(topics|topic\|.*|file\|.*)$"
)
topic_command_handler = CommandHandler('topic', topic_command)
