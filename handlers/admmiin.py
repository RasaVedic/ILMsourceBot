import os
import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)
from utils.fileops import get_message

# States
ADMIN_MENU, ADD_TOPIC, ADD_CONTENT_TOPIC, ADD_CONTENT_TYPE, ADD_CONTENT_DATA, ADD_MEME = range(6)

# --- Admin Menu Handler ---

async def admin_menu(update, context):
    user_id = update.effective_user.id
    admin_ids = context.bot_data.get('admin_ids', [])
    if user_id not in admin_ids:
        await update.message.reply_text("Sirf admin ke liye.")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Topic", callback_data='add_topic')],
        [InlineKeyboardButton("➕ Add Content", callback_data='add_content')],
        [InlineKeyboardButton("➕ Add Meme", callback_data='add_meme')],
        [InlineKeyboardButton("🚫 Show Banlist", callback_data='show_banlist')],
    ]
    await update.message.reply_text("Admin Menu:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_MENU

# --- Callback Handler: Admin Menu Buttons ---

async def admin_callback(update, context):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == 'add_topic':
        await query.edit_message_text("Naya topic ka naam bhejein:")
        return ADD_TOPIC
    elif data == 'add_content':
        from utils.fileops import get_topics
        topics = get_topics()
        if not topics:
            await query.edit_message_text("Koi topic nahi mila. Pehle topic add karein.")
            return ConversationHandler.END
        keyboard = [[InlineKeyboardButton(t, callback_data=f'addcontenttopic_{t}')] for t in topics]
        await query.edit_message_text("Kaunse topic me content add karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
        return ADD_CONTENT_TOPIC
    elif data == 'add_meme':
        await query.edit_message_text("Meme image bhejein (jpg/png):")
        return ADD_MEME
    elif data == 'show_banlist':
        try:
            with open('bans.json', 'r', encoding='utf-8') as f:
                bans = json.load(f)
            if not bans:
                await query.edit_message_text("Banlist empty hai.")
            else:
                text = "Banlist:\n" + "\n".join([str(uid) for uid in bans])
                await query.edit_message_text(text[:4000])  # telegram limit
        except Exception as e:
            await query.edit_message_text("Banlist read karne me error.")
        return ConversationHandler.END

# --- Add Topic (text input) ---

async def add_topic(update, context):
    topic = update.message.text.strip()
    topics_path = 'data/topic.txt'
    if os.path.exists(topics_path):
        with open(topics_path, 'r', encoding='utf-8') as f:
            topics = [t.strip() for t in f.readlines()]
    else:
        topics = []
    if topic in topics:
        await update.message.reply_text("Ye topic already hai.")
        return ConversationHandler.END
    with open(topics_path, 'a', encoding='utf-8') as f:
        f.write(topic+'\n')
    os.makedirs(f'data/reference/{topic}', exist_ok=True)
    await update.message.reply_text(f"Topic '{topic}' add ho gaya.")
    return ConversationHandler.END

# --- Add Content: Topic Choose (button) ---

async def add_content_topic(update, context):
    query = update.callback_query
    topic = query.data[len('addcontenttopic_'):]
    context.user_data['add_content_topic'] = topic
    keyboard = [
        [InlineKeyboardButton("Text", callback_data='type_text')],
        [InlineKeyboardButton("PDF", callback_data='type_pdf')],
        [InlineKeyboardButton("Image", callback_data='type_img')],
    ]
    await query.edit_message_text("Kis type ka content add karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_CONTENT_TYPE

# --- Add Content: File Type Choose (button) ---

async def add_content_type(update, context):
    query = update.callback_query
    data = query.data
    if data == 'type_text':
        context.user_data['add_content_type'] = 'text'
        await query.edit_message_text("Text bhejein (max 4000 chars):")
        return ADD_CONTENT_DATA
    elif data == 'type_pdf':
        context.user_data['add_content_type'] = 'pdf'
        await query.edit_message_text("PDF file bhejein (document upload karein):")
        return ADD_CONTENT_DATA
    elif data == 'type_img':
        context.user_data['add_content_type'] = 'img'
        await query.edit_message_text("Image bhejein (jpg/png upload karein):")
        return ADD_CONTENT_DATA

# --- Add Content: Data Receive (text/file) ---

async def add_content_data(update, context):
    topic = context.user_data.get('add_content_topic')
    ctype = context.user_data.get('add_content_type')
    folder = f'data/reference/{topic}'

    if ctype == 'text':
        text = update.message.text or ""
        filename = f'{topic}_{len(os.listdir(folder))+1}.txt'
        with open(os.path.join(folder, filename), 'w', encoding='utf-8') as f:
            f.write(text)
        await update.message.reply_text("Text content add ho gaya.")
    elif ctype == 'pdf' and update.message.document:
        file = await update.message.document.get_file()
        filename = update.message.document.file_name
        if not filename.lower().endswith('.pdf'):
            await update.message.reply_text("Sirf PDF file allow hai.")
            return
        await file.download_to_drive(custom_path=os.path.join(folder, filename))
        await update.message.reply_text("PDF add ho gaya.")
    elif ctype == 'img' and (update.message.photo or update.message.document):
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
            filename = f'{topic}_{len(os.listdir(folder))+1}.jpg'
        elif update.message.document:
            file = await update.message.document.get_file()
            filename = update.message.document.file_name
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                await update.message.reply_text("Sirf image (jpg/png) allow hai.")
                return
        await file.download_to_drive(custom_path=os.path.join(folder, filename))
        await update.message.reply_text("Image add ho gayi.")
    else:
        await update.message.reply_text("Content add nahi hua. Format galat ya file missing.")
    return ConversationHandler.END

# --- Add Meme: Meme image receive (photo/document) ---

async def add_meme(update, context):
    meme_folder = "data/memes"
    os.makedirs(meme_folder, exist_ok=True)
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        filename = f"meme_{len(os.listdir(meme_folder))+1}.jpg"
    elif update.message.document:
        file = await update.message.document.get_file()
        filename = update.message.document.file_name
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            await update.message.reply_text("Sirf image (jpg/png) allow hai.")
            return ConversationHandler.END
    else:
        await update.message.reply_text("File missing ya format galat.")
        return ConversationHandler.END
    await file.download_to_drive(custom_path=os.path.join(meme_folder, filename))
    await update.message.reply_text("Meme add ho gaya!")
    return ConversationHandler.END

# --- Conversation Handler Setup ---

def admin_conversation_handler(admin_ids):
    return ConversationHandler(
        entry_points=[CommandHandler("admin", admin_menu)],
        states={
            ADMIN_MENU: [CallbackQueryHandler(admin_callback)],
            ADD_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_topic)],
            ADD_CONTENT_TOPIC: [CallbackQueryHandler(add_content_topic)],
            ADD_CONTENT_TYPE: [CallbackQueryHandler(add_content_type)],
            ADD_CONTENT_DATA: [
                MessageHandler(filters.TEXT, add_content_data),
                MessageHandler(filters.Document.ALL, add_content_data),
                MessageHandler(filters.PHOTO, add_content_data),
            ],
            ADD_MEME: [
                MessageHandler(filters.PHOTO, add_meme),
                MessageHandler(filters.Document.IMAGE, add_meme),
            ],
        },
        fallbacks=[],
        per_user=True,
        per_chat=True,
    )
