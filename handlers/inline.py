import os
import uuid
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import InlineQueryHandler

def search_data_recursive(keyword):
    results = []
    keyword_lower = keyword.lower()
    for root, _, files in os.walk('data/reference'):
        topic = os.path.relpath(root, 'data/reference')
        for file in files:
            file_lower = file.lower()
            full_path = os.path.join(root, file)
            # Filename match
            if keyword_lower in file_lower:
                results.append((topic, file, None))
                continue
            # Text file content match
            if file_lower.endswith('.txt'):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if keyword_lower in content.lower():
                        start = content.lower().find(keyword_lower)
                        snippet = content[max(0, start-30):start+70].replace('\n', ' ')
                        results.append((topic, file, snippet))
                except Exception:
                    pass
    return results

async def inline_query_handler(update, context):
    user = update.inline_query.from_user
    query = update.inline_query.query.strip()
    results = []
    if not query:
        await update.inline_query.answer([])
        return
    matches = search_data_recursive(query)
    for topic, filename, snippet in matches[:30]:
        display_title = f"{topic} | {filename}"
        if snippet:
            description = snippet
        else:
            description = "👆FILE DEKHNE KE LIYE TAP KARKE SEND KAREIN."
        # Suggest the /getfile command with topic/filename for copy-paste
        cmd = f"/getfile {topic} {filename}"
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=display_title,
                description=description,
                input_message_content=InputTextMessageContent(
                    f"File: {topic}/{filename}\n👇👇NICHE TAP KARKE SEND KAREIN:\n<code>{cmd}</code>\n\n{description}",
                    parse_mode='HTML'
                )
            )
        )
    if not results:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="Koi result nahi mila",
                input_message_content=InputTextMessageContent("Koi result nahi mila")
            )
        )
    await update.inline_query.answer(results, cache_time=1)

inline_query_handler = InlineQueryHandler(inline_query_handler)
