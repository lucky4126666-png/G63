import os
import time
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

memory = {}
last_ai = {}

async def ask_ai(user_id, text):
    # anti spam
    if user_id in last_ai and time.time() - last_ai[user_id] < 2:
        return "⏳ Đợi 1 chút..."

    last_ai[user_id] = time.time()

    if user_id not in memory:
        memory[user_id] = [
            {
                "role": "system",
                "content": "Bạn là AI Telegram thông minh, trả lời tự nhiên, ngắn gọn."
            }
        ]

    memory[user_id].append({"role": "user", "content": text})

    if len(memory[user_id]) > 20:
        memory[user_id] = memory[user_id][-10:]

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=memory[user_id]
    )

    reply = res.choices[0].message.content

    memory[user_id].append({"role": "assistant", "content": reply})

    return reply
