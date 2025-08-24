
import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# --- aapka async getfile_handler (as function) yahi rahega ---

async def getfile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /getfile <topic> <filename>")
        return

    ref_base = os.path.join("data", "reference")
    all_topics = os.listdir(ref_base)

    # Attempt to find the longest topic match from args
    found = False
    for i in range(len(context.args), 0, -1):
        maybe_topic = " ".join(context.args[:i])
        if maybe_topic in all_topics:
            topic = maybe_topic
            filename = " ".join(context.args[i:])
            found = True
            break
    if not found:
        available_topics = "\n".join(all_topics)
        await update.message.reply_text(
            f"❌ Topic folder nahi mila.\nAvailable topics are:\n{available_topics}"
        )
        return

    dir_path = os.path.join(ref_base, topic)
    filepath = os.path.join(dir_path, filename)

    if not os.path.exists(filepath):
        files = "\n".join(os.listdir(dir_path))
        await update.message.reply_text(
            f"❌ File '{filename}' nahi mila.\n'[{topic}]' folder me yeh files hain:\n{files}"
        )
        return

    filetype = filename.split('.')[-1].lower()
    try:
        if filetype in ('jpg', 'jpeg', 'png'):
            with open(filepath, 'rb') as imgf:
                await update.message.reply_photo(photo=imgf, caption=filename)
        elif filetype == 'pdf':
            with open(filepath, 'rb') as pdff:
                await update.message.reply_document(document=pdff, filename=filename, caption=filename)
        elif filetype == 'txt':
            with open(filepath, 'r', encoding='utf-8') as txtf:
                text = txtf.read()
            await update.message.reply_text(f"📄 {filename}:\n\n{text[:4000]}")
        else:
            await update.message.reply_text("❌ Ye file type supported nahi hai.")
    except Exception as e:
        await update.message.reply_text(f"❌ File bhejne me error: {e}")

# --- YEH LINE ZARUR ADD KAREIN final line par ---
getfile_handler = CommandHandler('getfile', getfile_handler)
