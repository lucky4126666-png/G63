import os
import time
from openai import OpenAI
from db import get_conn

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise Exception("❌ OPENAI_API_KEY missing")

client = OpenAI(api_key=API_KEY)

last_call = {}


def load_memory(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()

    messages = [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    if not messages:
        messages = [{"role": "system", "content": "Bạn là AI Telegram thông minh."}]

    return messages


def save_message(user_id, role, content):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages(user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content)
    )

    conn.commit()
    conn.close()


async def ask_ai(user_id, text):
    now = time.time()

    if user_id in last_call and now - last_call[user_id] < 1:
        return "⏳ Đợi chút..."

    last_call[user_id] = now

    messages = load_memory(user_id)
    messages.append({"role": "user", "content": text})

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    reply = res.choices[0].message.content

    save_message(user_id, "user", text)
    save_message(user_id, "assistant", reply)

    return reply
