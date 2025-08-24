import os
import random

MEME_FOLDER = "data/memes"

async def send_daily_meme(context):
    chat_id = context.job.data["chat_id"]
    files = [f for f in os.listdir(MEME_FOLDER)
             if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if not files:
        return
    num_memes = min(1, len(files))  # 1 meme per job
    selected = random.sample(files, num_memes)
    for fname in selected:
        path = os.path.join(MEME_FOLDER, fname)
        with open(path, 'rb') as f:
            await context.bot.send_photo(chat_id=chat_id, photo=f, caption="Daily Meme")
