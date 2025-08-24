import json
import os
import logging
import sys
from datetime import time
from telegram.ext import ApplicationBuilder, CommandHandler
from handlers.control import stopbot_cmd, restartbot_cmd
#from telegram.ext import CommandHandler
from handlers.start import start_handler
from handlers.topic import topic_handler, topic_command_handler
from handlers.inline import inline_query_handler
from handlers.getfile import getfile_handler
from handlers.warn import (
    moderation_text_handler,
    warn_handler,
    warnings_handler,
    resetwarn_handler,
    setlimit_handler,
    setduration_handler,
)
#from proxy_manager import get_proxy_for_bot, rotate_ip,
#from proxy_manager import get_proxy_for_bot, start_auto_rotation
from handlers.admin import admin_conversation_handler
from handlers.meme import meme_handler, meme_button_handler, send_daily_meme
from handlers.general import help_handler, about_handler, alert_handler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_config(config_path='config.json'):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Config error: {e}")
        sys.exit(1)

CONFIG_PATH = os.getenv('CONFIG_PATH', 'config.json')
config = load_config(CONFIG_PATH)
admin_ids = config.get('admin_ids', [])
group_or_channel_id = config.get("group_or_channel_id")  # For daily meme

def main():
#    proxy = get_proxy_for_bot()
    #start_auto_rotation(interval_hours=1.5)  # 1.5 hours rotation
 ###   proxy = get_proxy_for_bot()  # initial proxy for bot

 #   rotate_ip()
    app = ApplicationBuilder().token(config['bot_token']).build()
    app.bot_data["admin_ids"] = admin_ids

    #app.add_handler(admin_conversation_handler(admin_ids=admin_ids))
#    app.add_handler(admin_conversation_handler(admin_ids=admin_ids))
    app.add_handler(admin_conversation_handler()) 
    app.add_handler(start_handler)
    app.add_handler(topic_handler)           # Yeh topic buttons ke liye (pattern laga hoga!)
    app.add_handler(meme_handler)            # /meme command
    app.add_handler(meme_button_handler)     # Meme button (callback_data="meme")
    app.add_handler(inline_query_handler)
    app.add_handler(getfile_handler)
#    app.add_handler(warn_handler)
    app.add_handler(help_handler)
    app.add_handler(about_handler)
    app.add_handler(alert_handler)
    app.add_handler(topic_command_handler)
    app.add_handler(moderation_text_handler)     # auto filter (delete + warn)
    app.add_handler(warn_handler)                # /warn
    app.add_handler(warnings_handler)            # /warnings
    app.add_handler(resetwarn_handler)           # /resetwarn
    app.add_handler(setlimit_handler)            # /setlimit
    app.add_handler(setduration_handler)         # /setduration
    app.add_handler(CommandHandler("stopbot", stopbot_cmd))
    app.add_handler(CommandHandler("restartbot", restartbot_cmd))

    if group_or_channel_id:
        app.job_queue.run_daily(
            send_daily_meme,
            time=time(hour=9, minute=0),
            days=range(7),
            name="daily_meme_morning",
            data={"chat_id": group_or_channel_id}
        )
        app.job_queue.run_daily(
            send_daily_meme,
            time=time(hour=18, minute=0),
            days=range(7),
            name="daily_meme_evening",
            data={"chat_id": group_or_channel_id}
        )
    else:
        logger.warning("group_or_channel_id not set in config.json. Daily memes will not be sent.")

    logger.info("✅ Bot running...")
    app.run_polling()

if __name__ == '__main__':
    main()
