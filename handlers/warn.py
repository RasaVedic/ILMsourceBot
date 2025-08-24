import os, json, re
from datetime import datetime, timedelta, timezone
from telegram import ChatPermissions, Update
from telegram.ext import (
    CommandHandler, MessageHandler, ContextTypes, filters
)

WARN_DB = os.path.join("data", "warnings.json")
BADWORDS_FILE = os.path.join("data", "badwords.txt")

DEFAULT_LIMIT = 3          # default warnings to action
DEFAULT_DURATION_H = 24    # default mute/ban hours


#from telegram import Update
#from telegram.ext import ContextTypes

async def check_ban_and_block(update_obj, context: ContextTypes.DEFAULT_TYPE):
    # Determine user_id based on type
    if hasattr(update_obj, "callback_query") and update_obj.callback_query is not None:
        user_id = update_obj.callback_query.from_user.id
    elif hasattr(update_obj, "from_user"):
        user_id = update_obj.from_user.id
    elif hasattr(update_obj, "effective_user"):
        user_id = update_obj.effective_user.id
    else:
        # Fallback, unknown type
        return False

    # Dummy banned users list
    banned_users = []  # e.g., [123456789, 987654321]

    if user_id in banned_users:
        # If banned, send message
        if hasattr(update_obj, "callback_query") and update_obj.callback_query is not None:
            await update_obj.callback_query.message.reply_text("🚫 Aap banned user ho, access denied.")
        elif hasattr(update_obj, "message"):
            await update_obj.message.reply_text("🚫 Aap banned user ho, access denied.")
        return True

    return False 
# --- storage utils ---
def _now():
    # use UTC to avoid tz pain
    return datetime.now(timezone.utc)

def _load_db():
    if os.path.exists(WARN_DB):
        with open(WARN_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_db(db):
    os.makedirs(os.path.dirname(WARN_DB), exist_ok=True)
    with open(WARN_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def _get_chat_cfg(db, chat_id):
    str_id = str(chat_id)
    if str_id not in db:
        db[str_id] = {
            "_config": {"limit": DEFAULT_LIMIT, "duration_h": DEFAULT_DURATION_H},
            "_mutes": {},   # for private "mute until" per user
            "_users": {}    # user_id -> {count, last_reset_iso}
        }
    return db[str_id]

def _reset_if_expired(user_rec):
    # auto reset count after 24h from last_reset
    last_reset = datetime.fromisoformat(user_rec.get("last_reset_iso"))
    if _now() - last_reset >= timedelta(hours=24):
        user_rec["count"] = 0
        user_rec["last_reset_iso"] = _now().isoformat()

def _inc_warn(db, chat_id, user_id):
    chat = _get_chat_cfg(db, chat_id)
    users = chat["_users"]
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"count": 0, "last_reset_iso": _now().isoformat()}
    _reset_if_expired(users[uid])
    users[uid]["count"] += 1
    return users[uid]["count"], chat["_config"]["limit"], chat["_config"]["duration_h"]

def _set_warn(db, chat_id, user_id, count):
    chat = _get_chat_cfg(db, chat_id)
    users = chat["_users"]
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"count": 0, "last_reset_iso": _now().isoformat()}
    users[uid]["count"] = count
    return users[uid]["count"]

def _get_warn(db, chat_id, user_id):
    chat = _get_chat_cfg(db, chat_id)
    users = chat["_users"]
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"count": 0, "last_reset_iso": _now().isoformat()}
    _reset_if_expired(users[uid])
    return users[uid]["count"], chat["_config"]["limit"], chat["_config"]["duration_h"]

def _set_config(db, chat_id, limit=None, duration_h=None):
    chat = _get_chat_cfg(db, chat_id)
    if limit is not None:
        chat["_config"]["limit"] = int(limit)
    if duration_h is not None:
        chat["_config"]["duration_h"] = int(duration_h)
    return chat["_config"]["limit"], chat["_config"]["duration_h"]

def _set_private_mute_until(db, chat_id, user_id, until_dt):
    chat = _get_chat_cfg(db, chat_id)
    chat["_mutes"][str(user_id)] = until_dt.isoformat()

def _get_private_mute_until(db, chat_id, user_id):
    chat = _get_chat_cfg(db, chat_id)
    iso = chat["_mutes"].get(str(user_id))
    return datetime.fromisoformat(iso) if iso else None

# --- badwords / banned emojis ---
def _load_badwords():
    words = set()
    if os.path.exists(BADWORDS_FILE):
        with open(BADWORDS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                w = line.strip()
                if w:
                    words.add(w.lower())
    return words

BANNED_EMOJIS = {"🖕"}  # extend as needed

def _is_abusive(text, badwords):
    lower = text.lower()
    # word match
    for w in badwords:
        # word boundary-ish check
        if re.search(rf"(^|\W){re.escape(w)}(\W|$)", lower):
            return True
    # banned emoji
    return any(e in text for e in BANNED_EMOJIS)

def _is_admin_user(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    # uses admin_ids from app.bot_data
    admin_ids = context.application.bot_data.get("admin_ids", [])
    return user_id in admin_ids

# --- moderation text handler (auto filter) ---
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.text is None:
        return

    chat = update.effective_chat
    user = update.effective_user
    text = update.message.text

    # respect private mutes: in private chat, if muted, ignore
    if chat.type == "private":
        db = _load_db()
        until = _get_private_mute_until(db, chat.id, user.id)
        if until and _now() < until:
            # ignore silently
            return

    badwords = _load_badwords()
    if not badwords:
        # if file missing/empty, do nothing
        return

    if _is_admin_user(context, user.id):
        return  # admins not filtered

    if not _is_abusive(text, badwords):
        return

    # abusive detected
    db = _load_db()
    new_count, limit, duration_h = _inc_warn(db, chat.id, user.id)
    _save_db(db)

    # try delete in groups
    if chat.type in ("group", "supergroup"):
        try:
            await update.message.delete()
        except:
            pass

    # warning message
    warn_msg = f"⚠️ Warning {new_count}/{limit}: Be respectful."
    try:
        await update.effective_chat.send_message(
            warn_msg, reply_to_message_id=update.message.message_id if chat.type != "private" else None
        )
    except:
        # fallback
        await context.bot.send_message(chat_id=chat.id, text=warn_msg)

    if new_count >= limit:
        # action
        if chat.type in ("group", "supergroup"):
            # ban for duration
            until_date = _now() + timedelta(hours=duration_h)
            try:
                await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id, until_date=until_date)
                await context.bot.send_message(chat_id=chat.id,
                    text=f"🚫 @{user.username or user.id} banned for {duration_h}h (reached {limit} warnings).")
            except:
                await context.bot.send_message(chat_id=chat.id,
                    text=f"❌ Failed to ban @{user.username or user.id}. Check bot admin rights.")
        else:
            # private "mute": bot will ignore for duration
            until = _now() + timedelta(hours=duration_h)
            _set_private_mute_until(db, chat.id, user.id, until)
            _save_db(db)
            try:
                await context.bot.send_message(chat_id=chat.id,
                    text=f"🤐 You are muted for {duration_h}h (reached {limit} warnings).")
            except:
                pass

# --- /warn @user reason ---
async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    chat = update.effective_chat
    user = update.effective_user

    if not _is_admin_user(context, user.id):
        await update.message.reply_text("❌ Only admins can use /warn.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /warn @username reason")
        return

    target_mention = context.args[0]
    reason = " ".join(context.args[1:])

    # resolve target user id (prefer reply_to)
    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif target_mention.startswith("@"):
        # Not always resolvable without user in chat; use username string as key fallback
        # For consistency with auto system, we need user_id. If not available, bail.
        await update.message.reply_text("Reply to a user's message with /warn to target them.")
        return
    else:
        await update.message.reply_text("Usage: /warn @username reason (or reply to a message).")
        return

    db = _load_db()
    new_count, limit, duration_h = _inc_warn(db, chat.id, target_user.id)
    _save_db(db)

    await update.message.reply_text(
        f"⚠️ Warning {new_count}/{limit} issued to @{target_user.username or target_user.id}\nReason: {reason}"
    )

    if new_count >= limit:
        if chat.type in ("group", "supergroup"):
            until_date = _now() + timedelta(hours=duration_h)
            try:
                await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_user.id, until_date=until_date)
                await update.message.reply_text(
                    f"🚫 @{target_user.username or target_user.id} banned for {duration_h}h (limit reached)."
                )
            except:
                await update.message.reply_text("❌ Failed to ban (bot might lack rights).")
        else:
            until = _now() + timedelta(hours=duration_h)
            _set_private_mute_until(db, chat.id, target_user.id, until)
            _save_db(db)
            await update.message.reply_text(f"🤐 Muted for {duration_h}h (limit reached).")

# --- /warnings @user ---
async def warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    chat = update.effective_chat
    user = update.effective_user

    if not _is_admin_user(context, user.id):
        await update.message.reply_text("❌ Only admins can use /warnings.")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args and context.args[0].startswith("@"):
        await update.message.reply_text("Reply to a user's message to check warnings.")
        return
    else:
        await update.message.reply_text("Reply to a user's message to check warnings.")
        return

    db = _load_db()
    count, limit, duration_h = _get_warn(db, chat.id, target_user.id)
    await update.message.reply_text(
        f"ℹ️ Warnings for @{target_user.username or target_user.id}: {count}/{limit} (action {duration_h}h)"
    )

# --- /resetwarn @user ---
async def resetwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    chat = update.effective_chat
    user = update.effective_user

    if not _is_admin_user(context, user.id):
        await update.message.reply_text("❌ Only admins can use /resetwarn.")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    else:
        await update.message.reply_text("Reply to a user's message to reset warnings.")
        return

    db = _load_db()
    newc = _set_warn(db, chat.id, target_user.id, 0)
    _save_db(db)
    await update.message.reply_text(f"✅ Warnings reset for @{target_user.username or target_user.id} (now {newc}).")

# --- /setlimit N ---
async def setlimit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not _is_admin_user(context, user.id):
        await update.message.reply_text("❌ Only admins can use /setlimit.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /setlimit <number>")
        return
    db = _load_db()
    limit, dur = _set_config(db, chat.id, limit=int(context.args[0]))
    _save_db(db)
    await update.message.reply_text(f"✅ Warning limit set to {limit} (duration {dur}h).")

# --- /setduration H ---
async def setduration_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not _is_admin_user(context, user.id):
        await update.message.reply_text("❌ Only admins can use /setduration.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /setduration <hours>")
        return
    db = _load_db()
    limit, dur = _set_config(db, chat.id, duration_h=int(context.args[0]))
    _save_db(db)
    await update.message.reply_text(f"✅ Action duration set to {dur}h (limit {limit}).")

# --- handlers to export ---
moderation_text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, on_text)
warn_handler = CommandHandler("warn", warn_cmd)
warnings_handler = CommandHandler("warnings", warnings_cmd)
resetwarn_handler = CommandHandler("resetwarn", resetwarn_cmd)
setlimit_handler = CommandHandler("setlimit", setlimit_cmd)
setduration_handler = CommandHandler("setduration", setduration_cmd)
