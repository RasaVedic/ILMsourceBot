import os
import json
import shutil
from zipfile import ZipFile
from typing import List, Tuple
#from config import admin_ids
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

# ============
# PATHS & CONST
# ============
import os

# Paths & constants
CONFIG_PATH = "config.json"
TOPIC_TXT   = os.path.join("data", "topic.txt")
REF_DIR     = os.path.join("data", "reference")
MEME_DIR    = os.path.join("data", "memes")
HELP_TXT    = os.path.join("messages", "admin_commands.txt")
BANLIST_JSON= "bans.json"
BACKUPS_DIR = "Backups"

# Make sure directories exist
#os.makedirs(REF_DIR, exist_ok=True)
#os.makedirs(MEME_DIR, exist_ok=True)
#os.makedirs(BACKUPS_DIR, exist_ok=True)


# Conversation states
(
    ADMIN_MENU,
    ADD_TOPIC,
    EDIT_TOPIC_PICK, EDIT_TOPIC_NEW,
    REMOVE_TOPIC_PICK,
    ADD_CONTENT_TOPIC, ADD_CONTENT_TYPE, ADD_CONTENT_DATA,
    LIST_CONTENT_TOPIC,
    REMOVE_CONTENT_TOPIC, REMOVE_CONTENT_PICK_FILE,
    RENAME_CONTENT_TOPIC, RENAME_CONTENT_PICK_FILE, RENAME_CONTENT_NEWNAME,
    ADD_MEME_WAIT,
    REMOVE_MEME_WAIT_INDEX,
) = range(16)

# memory for admin-mode sessions (user_id -> bool)
ADMIN_SESSIONS = {}
#open dir logic
#import json

def get_admin_ids(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config_data = json.load(file)
            admin_ids = config_data.get("admin_ids", [])
            return admin_ids
    except FileNotFoundError:
        print(f"Error: {config_path} file not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: {config_path} contains invalid JSON.")
        return []

# Usage example:
admin_ids = get_admin_ids(CONFIG_PATH)
print("Admin IDs:", admin_ids)

# ===============
# Helpers / Utils
# ===============
def _ensure_dirs():
    os.makedirs(os.path.dirname(TOPIC_TXT), exist_ok=True)
    os.makedirs(REF_DIR, exist_ok=True)
    os.makedirs(MEME_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(HELP_TXT), exist_ok=True)
    os.makedirs(BACKUPS_DIR, exist_ok=True)

def _load_admin_ids() -> List[int]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("admin_ids", [])
    except Exception:
        return []

def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in _load_admin_ids()

def _require_admin_mode(update: Update) -> Tuple[bool, int]:
    uid = update.effective_user.id if update.effective_user else None
    in_mode = ADMIN_SESSIONS.get(uid, False)
    return in_mode, uid

def _read_topics() -> List[str]:
    if not os.path.exists(TOPIC_TXT):
        return []
    with open(TOPIC_TXT, "r", encoding="utf-8") as f:
        return [t.strip() for t in f if t.strip()]

def _write_topics(topics: List[str]):
    os.makedirs(os.path.dirname(TOPIC_TXT), exist_ok=True)
    with open(TOPIC_TXT, "w", encoding="utf-8") as f:
        for t in topics:
            f.write(t + "\n")

def _topic_keyboard(prefix: str) -> InlineKeyboardMarkup:
    topics = _read_topics()
    if not topics:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ No topics", callback_data="noop")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=f"{prefix}{t}")]
                                 for t in topics])

def _admin_home_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("➕ Add Topic", callback_data="btn_add_topic"),
         InlineKeyboardButton("✏️ Edit Topic", callback_data="btn_edit_topic")],
        [InlineKeyboardButton("🗑 Remove Topic", callback_data="btn_remove_topic"),
         InlineKeyboardButton("📚 List Topics", callback_data="btn_list_topics")],

        [InlineKeyboardButton("📝 Add Content", callback_data="btn_add_content"),
         InlineKeyboardButton("🧾 List Content", callback_data="btn_list_content")],
        [InlineKeyboardButton("🗑 Remove Content", callback_data="btn_remove_content"),
         InlineKeyboardButton("📝 Rename Content", callback_data="btn_rename_content")],

        [InlineKeyboardButton("😂 Add Meme", callback_data="btn_add_meme"),
         InlineKeyboardButton("🗑 Remove Meme", callback_data="btn_remove_meme")],
        [InlineKeyboardButton("📸 List Memes", callback_data="btn_list_memes")],

        [InlineKeyboardButton("🚫 Show Banlist", callback_data="btn_show_banlist"),
         InlineKeyboardButton("🗂 Backup", callback_data="btn_backup")],

        [InlineKeyboardButton("❔ Help", callback_data="btn_help"),
         InlineKeyboardButton("❌ Exit", callback_data="btn_exit")],
    ]
    return InlineKeyboardMarkup(rows)

async def _send_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Admin Commands:\n"
        "- /admin (enter), /exit (leave), /admin_help (this)\n"
        "- Topic: /add_topic /edit_topic /remove_topic /list_topics\n"
        "- Content: /add_content /list_content /remove_content /rename_content\n"
        "- Memes: /add_meme /list_memes /remove_meme\n"
        "- Banlist: /show_banlist\n"
        "- /backup\n"
    )
    try:
        if os.path.exists(HELP_TXT):
            with open(HELP_TXT, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if raw:
                text = raw
    except Exception:
        pass

    if update.effective_message:
        await update.effective_message.reply_text(text[:4000])

def _list_files_in_topic(topic: str) -> List[str]:
    folder = os.path.join(REF_DIR, topic)
    if not os.path.exists(folder):
        return []
    return sorted([fn for fn in os.listdir(folder) if os.path.isfile(os.path.join(folder, fn))])

# =====================
# Admin Mode: /admin, /exit, /admin_help
# =====================
async def admin_enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Admin IDs from config:", admin_ids)
    print("User ID from update:", update.effective_user.id)
    _ensure_dirs()
    if not _is_admin(update):
        await update.message.reply_text("⛔ Ye feature sirf admins ke liye hai.")
        return ConversationHandler.END

    uid = update.effective_user.id
    ADMIN_SESSIONS[uid] = True
    await update.message.reply_text("✅ Admin Mode ON. (/admin_help dekh lo)")
    await update.message.reply_text("Admin Menu:", reply_markup=_admin_home_kb())
    return ADMIN_MENU

async def admin_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END
    uid = update.effective_user.id
    ADMIN_SESSIONS[uid] = False
    await update.message.reply_text("❌ Admin Mode OFF.")
    return ConversationHandler.END

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    in_mode, _ = _require_admin_mode(update)
    if not _is_admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END
    if not in_mode:
        await update.message.reply_text("ℹ️ Pehle /admin likho (mode on).")
        return ConversationHandler.END
    await _send_help(update, context)
    return ADMIN_MENU

# =====================
# Admin Menu Button Router
# =====================
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        return ConversationHandler.END

    q = update.callback_query
    await q.answer()
    data = q.data

    # Topics
    if data == "btn_add_topic":
        await q.edit_message_text("🆕 Naya topic ka naam bhejein:")
        return ADD_TOPIC

    if data == "btn_edit_topic":
        await q.edit_message_text("✏️ Rename ke liye topic choose karein:", reply_markup=_topic_keyboard("editpick_"))
        return EDIT_TOPIC_PICK

    if data == "btn_remove_topic":
        await q.edit_message_text("🗑 Delete ke liye topic choose karein:", reply_markup=_topic_keyboard("removepick_"))
        return REMOVE_TOPIC_PICK

    if data == "btn_list_topics":
        topics = _read_topics()
        txt = "📚 Topics:\n" + ("\n".join(f"- {t}" for t in topics) if topics else "❌ None")
        await q.edit_message_text(txt[:4000], reply_markup=_admin_home_kb())
        return ADMIN_MENU

    # Content
    if data == "btn_add_content":
        await q.edit_message_text("📝 Kaunse topic me content add karna hai?", reply_markup=_topic_keyboard("addcontenttopic_"))
        return ADD_CONTENT_TOPIC

    if data == "btn_list_content":
        await q.edit_message_text("🧾 Kis topic ka content dekhna hai?", reply_markup=_topic_keyboard("listcontent_"))
        return LIST_CONTENT_TOPIC

    if data == "btn_remove_content":
        await q.edit_message_text("🗑 Kis topic se file delete karni hai?", reply_markup=_topic_keyboard("remcontenttopic_"))
        return REMOVE_CONTENT_TOPIC

    if data == "btn_rename_content":
        await q.edit_message_text("📝 Kis topic me file rename karni hai?", reply_markup=_topic_keyboard("renamecontenttopic_"))
        return RENAME_CONTENT_TOPIC

    # Memes
    if data == "btn_add_meme":
        await q.edit_message_text("😂 Meme image bhejein (jpg/png as photo/document):")
        return ADD_MEME_WAIT

    if data == "btn_remove_meme":
        files = sorted(os.listdir(MEME_DIR)) if os.path.exists(MEME_DIR) else []
        if not files:
            await q.edit_message_text("❌ Koi meme nahi.", reply_markup=_admin_home_kb())
            return ADMIN_MENU
        listing = "\n".join(f"{i+1}. {fn}" for i, fn in enumerate(files[:200]))
        await q.edit_message_text(
            f"🗑 Kaunsa meme delete karna hai? Index bhejein (1..{len(files)}):\n\n{listing}"[:4000]
        )
        return REMOVE_MEME_WAIT_INDEX

    if data == "btn_list_memes":
        files = sorted(os.listdir(MEME_DIR)) if os.path.exists(MEME_DIR) else []
        txt = "📸 Memes:\n" + ("\n".join(f"- {f}" for f in files) if files else "❌ None")
        await q.edit_message_text(txt[:4000], reply_markup=_admin_home_kb())
        return ADMIN_MENU

    # Banlist
    if data == "btn_show_banlist":
        try:
            if os.path.exists(BANLIST_JSON):
                with open(BANLIST_JSON, "r", encoding="utf-8") as f:
                    bans = json.load(f)
            else:
                bans = []
            txt = "🚫 Banlist:\n" + ("\n".join(str(x) for x in bans) if bans else "Empty")
            await q.edit_message_text(txt[:4000], reply_markup=_admin_home_kb())
        except Exception:
            await q.edit_message_text("⚠️ Banlist read error.", reply_markup=_admin_home_kb())
        return ADMIN_MENU

    # Backup
    if data == "btn_backup":
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        zip_path = os.path.join(BACKUPS_DIR, "backup.zip")
        with ZipFile(zip_path, "w") as z:
            for base in ("Data", "Messages"):
                if os.path.exists(base):
                    for root, _, files in os.walk(base):
                        for f in files:
                            full = os.path.join(root, f)
                            arc = os.path.relpath(full, ".")
                            z.write(full, arc)
        await q.edit_message_text(f"✅ Backup created: {zip_path}", reply_markup=_admin_home_kb())
        return ADMIN_MENU

    # Help / Exit
    if data == "btn_help":
        await _send_help(update, context)
        await q.edit_message_reply_markup(reply_markup=_admin_home_kb())
        return ADMIN_MENU

    if data == "btn_exit":
        uid = update.effective_user.id
        ADMIN_SESSIONS[uid] = False
        await q.edit_message_text("❌ Admin Mode OFF.")
        return ConversationHandler.END

    # Unknown
    await q.edit_message_text("⚠️ Unknown action.", reply_markup=_admin_home_kb())
    return ADMIN_MENU

# ==============
# TOPIC handlers
# ==============
async def add_topic_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END

    topic = (update.message.text or "").strip()
    if not topic:
        await update.message.reply_text("⚠️ Empty topic. Dubara bhejein:")
        return ADD_TOPIC

    topics = _read_topics()
    if topic in topics:
        await update.message.reply_text("❗ Ye topic already hai. Koi aur naam bhejein:")
        return ADD_TOPIC

    topics.append(topic)
    _write_topics(topics)
    os.makedirs(os.path.join(REF_DIR, topic), exist_ok=True)
    await update.message.reply_text(f"✅ Topic '{topic}' add ho gaya.", reply_markup=_admin_home_kb())
    return ADMIN_MENU

async def edit_topic_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("editpick_"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    old = q.data[len("editpick_"):]
    context.user_data["edit_old_topic"] = old
    await q.edit_message_text(f"✏️ Naya naam bhejein for: {old}")
    return EDIT_TOPIC_NEW

async def edit_topic_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    new_name = (update.message.text or "").strip()
    old = context.user_data.get("edit_old_topic")
    if not old or not new_name:
        await update.message.reply_text("⚠️ Invalid. Wapas menu.", reply_markup=_admin_home_kb())
        return ADMIN_MENU

    topics = _read_topics()
    if old not in topics:
        await update.message.reply_text("❌ Old topic nahi mila.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    if new_name in topics:
        await update.message.reply_text("❗ Ye naam already exist karta hai. Naya naam do:")
        return EDIT_TOPIC_NEW

    old_dir = os.path.join(REF_DIR, old)
    new_dir = os.path.join(REF_DIR, new_name)
    if os.path.exists(old_dir):
        os.rename(old_dir, new_dir)

    topics = [new_name if t == old else t for t in topics]
    _write_topics(topics)
    await update.message.reply_text(f"✅ Rename: '{old}' → '{new_name}'", reply_markup=_admin_home_kb())
    return ADMIN_MENU

async def remove_topic_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("removepick_"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    topic = q.data[len("removepick_"):]
    topics = _read_topics()
    if topic in topics:
        topics.remove(topic)
        _write_topics(topics)
    folder = os.path.join(REF_DIR, topic)
    if os.path.exists(folder):
        shutil.rmtree(folder, ignore_errors=True)
    await q.edit_message_text(f"🗑 Topic '{topic}' delete ho gaya.", reply_markup=_admin_home_kb())
    return ADMIN_MENU

# =====================
# CONTENT handlers
# =====================
async def add_content_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("addcontenttopic_"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    topic = q.data[len("addcontenttopic_"):]
    context.user_data["add_content_topic"] = topic
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Text", callback_data="type_text")],
        [InlineKeyboardButton("PDF",  callback_data="type_pdf")],
        [InlineKeyboardButton("Image",callback_data="type_img")],
    ])
    await q.edit_message_text(f"Topic: {topic}\nKis type ka content add karna hai?", reply_markup=kb)
    return ADD_CONTENT_TYPE

async def add_content_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    data = q.data
    if data not in ("type_text", "type_pdf", "type_img"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    ctype = {"type_text":"text", "type_pdf":"pdf", "type_img":"img"}[data]
    context.user_data["add_content_type"] = ctype
    prompt = {
        "text": "📝 Text bhejein:",
        "pdf":  "📄 PDF document upload karein:",
        "img":  "🖼 Image bhejein (jpg/png):"
    }[ctype]
    await q.edit_message_text(prompt)
    return ADD_CONTENT_DATA

async def add_content_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    topic = context.user_data.get("add_content_topic")
    ctype = context.user_data.get("add_content_type")
    if not topic or not ctype:
        await update.message.reply_text("⚠️ Session lost. Wapas menu.", reply_markup=_admin_home_kb())
        return ADMIN_MENU

    folder = os.path.join(REF_DIR, topic)
    os.makedirs(folder, exist_ok=True)

    try:
        if ctype == "text":
            text = update.message.text or ""
            idx = len(os.listdir(folder)) + 1
            filename = f"{topic}_{idx}.txt"
            with open(os.path.join(folder, filename), "w", encoding="utf-8") as f:
                f.write(text)
            await update.message.reply_text("✅ Text content add ho gaya.", reply_markup=_admin_home_kb())
            return ADMIN_MENU

        if ctype == "pdf" and update.message.document:
            tgfile = await update.message.document.get_file()
            filename = update.message.document.file_name or "file.pdf"
            if not filename.lower().endswith(".pdf"):
                await update.message.reply_text("❌ Sirf PDF allow hai.")
                return ADD_CONTENT_DATA
            await tgfile.download_to_drive(custom_path=os.path.join(folder, filename))
            await update.message.reply_text("✅ PDF add ho gaya.", reply_markup=_admin_home_kb())
            return ADMIN_MENU

        if ctype == "img" and (update.message.photo or update.message.document):
            if update.message.photo:
                tgfile = await update.message.photo[-1].get_file()
                idx = len(os.listdir(folder)) + 1
                filename = f"{topic}_{idx}.jpg"
            else:
                tgfile = await update.message.document.get_file()
                filename = update.message.document.file_name or "image.jpg"
                if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    await update.message.reply_text("❌ Sirf image (jpg/png) allow hai.")
                    return ADD_CONTENT_DATA
            await tgfile.download_to_drive(custom_path=os.path.join(folder, filename))
            await update.message.reply_text("✅ Image add ho gayi.", reply_markup=_admin_home_kb())
            return ADMIN_MENU

        await update.message.reply_text("❌ Content add nahi hua. Sahi format bhejein.")
        return ADD_CONTENT_DATA
    except Exception:
        await update.message.reply_text("⚠️ Error: content save nahi ho paya.", reply_markup=_admin_home_kb())
        return ADMIN_MENU

# List content of a topic (button flow)
async def list_content_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("listcontent_"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    topic = q.data[len("listcontent_"):]
    files = _list_files_in_topic(topic)
    if not files:
        await q.edit_message_text(f"📂 {topic} (empty)", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    listing = "\n".join(f"- {fn}" for fn in files)
    await q.edit_message_text(f"📂 {topic} files:\n{listing}"[:4000], reply_markup=_admin_home_kb())
    return ADMIN_MENU

# Remove content: pick topic → pick file → delete
async def remove_content_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("remcontenttopic_"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    topic = q.data[len("remcontenttopic_"):]
    files = _list_files_in_topic(topic)
    if not files:
        await q.edit_message_text("❌ Koi file nahi.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    buttons = [[InlineKeyboardButton(fn, callback_data=f"remfile_{topic}::{fn}")] for fn in files[:100]]
    await q.edit_message_text("🗑 Kaunsi file delete karni hai?", reply_markup=InlineKeyboardMarkup(buttons))
    return REMOVE_CONTENT_PICK_FILE

async def remove_content_pick_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("remfile_"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    payload = q.data[len("remfile_"):]
    try:
        topic, fn = payload.split("::", 1)
    except ValueError:
        await q.edit_message_text("⚠️ Invalid payload.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    path = os.path.join(REF_DIR, topic, fn)
    if os.path.exists(path):
        try:
            os.remove(path)
            await q.edit_message_text(f"✅ Deleted: {fn}", reply_markup=_admin_home_kb())
        except Exception:
            await q.edit_message_text("⚠️ Delete failed.", reply_markup=_admin_home_kb())
    else:
        await q.edit_message_text("❌ File not found.", reply_markup=_admin_home_kb())
    return ADMIN_MENU

# Rename content: pick topic → pick file → send new name
async def rename_content_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("renamecontenttopic_"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    topic = q.data[len("renamecontenttopic_"):]
    context.user_data["rename_topic"] = topic
    files = _list_files_in_topic(topic)
    if not files:
        await q.edit_message_text("❌ Koi file nahi.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    buttons = [[InlineKeyboardButton(fn, callback_data=f"renamepick_{fn}")] for fn in files[:100]]
    await q.edit_message_text("📝 Kaunsi file rename karni hai?", reply_markup=InlineKeyboardMarkup(buttons))
    return RENAME_CONTENT_PICK_FILE

async def rename_content_pick_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    q = update.callback_query
    await q.answer()
    if not q.data.startswith("renamepick_"):
        await q.edit_message_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    fn = q.data[len("renamepick_"):]
    context.user_data["rename_old_file"] = fn
    await q.edit_message_text("🔤 Naya filename bhejein (extension ke sath):")
    return RENAME_CONTENT_NEWNAME

async def rename_content_newname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    newname = (update.message.text or "").strip()
    topic = context.user_data.get("rename_topic")
    oldfn = context.user_data.get("rename_old_file")
    if not topic or not oldfn or not newname:
        await update.message.reply_text("⚠️ Invalid.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    old = os.path.join(REF_DIR, topic, oldfn)
    new = os.path.join(REF_DIR, topic, newname)
    try:
        os.replace(old, new)
        await update.message.reply_text(f"✅ Renamed: {oldfn} → {newname}", reply_markup=_admin_home_kb())
    except Exception:
        await update.message.reply_text("⚠️ Rename failed.", reply_markup=_admin_home_kb())
    return ADMIN_MENU

# ============
# MEME handlers
# ============
async def add_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    os.makedirs(MEME_DIR, exist_ok=True)
    if update.message.photo:
        tgfile = await update.message.photo[-1].get_file()
        filename = f"meme_{len(os.listdir(MEME_DIR))+1}.jpg"
    elif update.message.document:
        tgfile = await update.message.document.get_file()
        filename = update.message.document.file_name or "meme.jpg"
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            await update.message.reply_text("❌ Sirf image (jpg/png) allow hai.")
            return ADD_MEME_WAIT
    else:
        await update.message.reply_text("⚠️ File missing ya format galat.")
        return ADD_MEME_WAIT
    await tgfile.download_to_drive(custom_path=os.path.join(MEME_DIR, filename))
    await update.message.reply_text("✅ Meme add ho gaya.", reply_markup=_admin_home_kb())
    return ADMIN_MENU

async def remove_meme_by_index(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    text = (update.message.text or "").strip()
    files = sorted(os.listdir(MEME_DIR)) if os.path.exists(MEME_DIR) else []
    if not files:
        await update.message.reply_text("❌ Koi meme nahi.", reply_markup=_admin_home_kb())
        return ADMIN_MENU
    if not text.isdigit():
        await update.message.reply_text("⚠️ Index (number) bhejein.")
        return REMOVE_MEME_WAIT_INDEX
    idx = int(text) - 1
    if idx < 0 or idx >= len(files):
        await update.message.reply_text("❌ Invalid index.")
        return REMOVE_MEME_WAIT_INDEX
    path = os.path.join(MEME_DIR, files[idx])
    try:
        os.remove(path)
        await update.message.reply_text(f"✅ Deleted: {files[idx]}", reply_markup=_admin_home_kb())
    except Exception:
        await update.message.reply_text("⚠️ Delete failed.", reply_markup=_admin_home_kb())
    return ADMIN_MENU

# =============
# SHORTCUT CMDS
# =============
async def cmd_admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await _send_help(update, context)
    return ADMIN_MENU

async def cmd_add_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await update.message.reply_text("🆕 Naya topic ka naam bhejein:")
    return ADD_TOPIC

async def cmd_edit_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await update.message.reply_text("✏️ Topic choose:", reply_markup=_topic_keyboard("editpick_"))
    return EDIT_TOPIC_PICK

async def cmd_remove_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await update.message.reply_text("🗑 Topic choose:", reply_markup=_topic_keyboard("removepick_"))
    return REMOVE_TOPIC_PICK

async def cmd_list_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    topics = _read_topics()
    txt = "📚 Topics:\n" + ("\n".join(f"- {t}" for t in topics) if topics else "❌ None")
    await update.message.reply_text(txt[:4000], reply_markup=_admin_home_kb())
    return ADMIN_MENU

async def cmd_add_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await update.message.reply_text("📝 Topic choose:", reply_markup=_topic_keyboard("addcontenttopic_"))
    return ADD_CONTENT_TOPIC

async def cmd_list_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await update.message.reply_text("🧾 Topic choose:", reply_markup=_topic_keyboard("listcontent_"))
    return LIST_CONTENT_TOPIC

async def cmd_remove_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await update.message.reply_text("🗑 Topic choose:", reply_markup=_topic_keyboard("remcontenttopic_"))
    return REMOVE_CONTENT_TOPIC

async def cmd_rename_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await update.message.reply_text("📝 Topic choose:", reply_markup=_topic_keyboard("renamecontenttopic_"))
    return RENAME_CONTENT_TOPIC

async def cmd_add_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    await update.message.reply_text("😂 Meme image bhejein (jpg/png):")
    return ADD_MEME_WAIT

async def cmd_list_memes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    files = sorted(os.listdir(MEME_DIR)) if os.path.exists(MEME_DIR) else []
    txt = "📸 Memes:\n" + ("\n".join(f"- {f}" for f in files) if files else "❌ None")
    await update.message.reply_text(txt[:4000], reply_markup=_admin_home_kb())
    return ADMIN_MENU

async def cmd_remove_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    files = sorted(os.listdir(MEME_DIR)) if os.path.exists(MEME_DIR) else []
    if not files:
        await update.message.reply_text("❌ Koi meme nahi.")
        return ADMIN_MENU
    listing = "\n".join(f"{i+1}. {fn}" for i, fn in enumerate(files[:200]))
    await update.message.reply_text(
        f"🗑 Kaunsa meme delete karna hai? Index bhejein (1..{len(files)}):\n\n{listing}"[:4000]
    )
    return REMOVE_MEME_WAIT_INDEX

async def cmd_show_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    try:
        if os.path.exists(BANLIST_JSON):
            with open(BANLIST_JSON, "r", encoding="utf-8") as f:
                bans = json.load(f)
        else:
            bans = []
        txt = "🚫 Banlist:\n" + ("\n".join(str(x) for x in bans) if bans else "Empty")
        await update.message.reply_text(txt[:4000], reply_markup=_admin_home_kb())
    except Exception:
        await update.message.reply_text("⚠️ Banlist read error.", reply_markup=_admin_home_kb())
    return ADMIN_MENU

async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return ConversationHandler.END
    in_mode, _ = _require_admin_mode(update)
    if not in_mode:
        await update.message.reply_text("ℹ️ /admin likho pehle.")
        return ConversationHandler.END
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    zip_path = os.path.join(BACKUPS_DIR, "backup.zip")
    with ZipFile(zip_path, "w") as z:
        for base in ("Data", "Messages"):
            if os.path.exists(base):
                for root, _, files in os.walk(base):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = os.path.relpath(full, ".")
                        z.write(full, arc)
    await update.message.reply_text(f"✅ Backup created: {zip_path}", reply_markup=_admin_home_kb())
    return ADMIN_MENU

# ==================
# Conversation Factory
# ==================
def admin_conversation_handler():
    """
    Register in main.py:
        from handlers.admin import admin_conversation_handler
        application.add_handler(admin_conversation_handler())

    Ensure: Telegrambot/config.json contains admin_ids list.
    """
    _ensure_dirs()
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_enter),
        ],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_buttons),

                # Shortcuts (only work while in admin mode)
                CommandHandler("admin_help", admin_help),
                CommandHandler("exit", admin_exit),

                CommandHandler("add_topic", cmd_add_topic),
                CommandHandler("edit_topic", cmd_edit_topic),
                CommandHandler("remove_topic", cmd_remove_topic),
                CommandHandler("list_topics", cmd_list_topics),

                CommandHandler("add_content", cmd_add_content),
                CommandHandler("list_content", cmd_list_content),
                CommandHandler("remove_content", cmd_remove_content),
                CommandHandler("rename_content", cmd_rename_content),

                CommandHandler("add_meme", cmd_add_meme),
                CommandHandler("list_memes", cmd_list_memes),
                CommandHandler("remove_meme", cmd_remove_meme),

                CommandHandler("show_banlist", cmd_show_banlist),
                CommandHandler("backup", cmd_backup),
            ],

            # Add topic (text)
            ADD_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_topic_text),
                CommandHandler("exit", admin_exit),
            ],

            # Edit topic
            EDIT_TOPIC_PICK: [
                CallbackQueryHandler(edit_topic_pick, pattern=r"^editpick_"),
                CommandHandler("exit", admin_exit),
            ],
            EDIT_TOPIC_NEW: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_topic_new),
                CommandHandler("exit", admin_exit),
            ],

            # Remove topic
            REMOVE_TOPIC_PICK: [
                CallbackQueryHandler(remove_topic_pick, pattern=r"^removepick_"),
                CommandHandler("exit", admin_exit),
            ],

            # Add content flow
            ADD_CONTENT_TOPIC: [
                CallbackQueryHandler(add_content_topic, pattern=r"^addcontenttopic_"),
                CommandHandler("exit", admin_exit),
            ],
            ADD_CONTENT_TYPE: [
                CallbackQueryHandler(add_content_type, pattern=r"^type_"),
                CommandHandler("exit", admin_exit),
            ],
            ADD_CONTENT_DATA: [
                MessageHandler(filters.TEXT, add_content_data),
                MessageHandler(filters.Document.ALL, add_content_data),
                MessageHandler(filters.PHOTO, add_content_data),
                CommandHandler("exit", admin_exit),
            ],

            # List content
            LIST_CONTENT_TOPIC: [
                CallbackQueryHandler(list_content_topic, pattern=r"^listcontent_"),
                CommandHandler("exit", admin_exit),
            ],

            # Remove content
            REMOVE_CONTENT_TOPIC: [
                CallbackQueryHandler(remove_content_topic, pattern=r"^remcontenttopic_"),
                CommandHandler("exit", admin_exit),
            ],
            REMOVE_CONTENT_PICK_FILE: [
                CallbackQueryHandler(remove_content_pick_file, pattern=r"^remfile_"),
                CommandHandler("exit", admin_exit),
            ],

            # Rename content
            RENAME_CONTENT_TOPIC: [
                CallbackQueryHandler(rename_content_topic, pattern=r"^renamecontenttopic_"),
                CommandHandler("exit", admin_exit),
            ],
            RENAME_CONTENT_PICK_FILE: [
                CallbackQueryHandler(rename_content_pick_file, pattern=r"^renamepick_"),
                CommandHandler("exit", admin_exit),
            ],
            RENAME_CONTENT_NEWNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_content_newname),
                CommandHandler("exit", admin_exit),
            ],

            # Memes
            ADD_MEME_WAIT: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, add_meme),
                CommandHandler("exit", admin_exit),
            ],
            REMOVE_MEME_WAIT_INDEX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, remove_meme_by_index),
                CommandHandler("exit", admin_exit),
            ],
        },
        fallbacks=[CommandHandler("exit", admin_exit)],
        per_user=True,
        per_chat=True,
#        per_message=True,
    )
