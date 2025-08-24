import os
import json

# Base data folder (absolute path)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

def get_message(filename, **kwargs):
    path = os.path.join(DATA_DIR, "..", "messages", filename + '.txt')
    with open(path, 'r', encoding='utf-8') as f:
        msg = f.read()
    return msg.format(**kwargs)

def get_topics():
    path = os.path.join(DATA_DIR, "topic.txt")
    with open(path, 'r', encoding='utf-8') as f:
        topics = [line.strip() for line in f if line.strip()]
    return topics

def get_topic_files(topic):
    path = os.path.join(DATA_DIR, "reference", topic.strip())
    if not os.path.isdir(path):
        return []
    # strip every filename, avoid hidden spaces/newlines
    return [f.strip() for f in os.listdir(path)]

def get_file_parts(filepath, max_chars=1500):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    parts = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
    return parts

async def alert_admin(context, username, error):
    with open(os.path.join(DATA_DIR, "..", "config.json"), 'r') as f:
        config = json.load(f)
    msg = get_message('alert_admin', username=username, error=error)
    for admin_id in config["admin_ids"]:
        try:
            await context.bot.send_message(admin_id, msg)
        except:
            pass
