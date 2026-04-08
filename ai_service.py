import os
import time
from openai import OpenAI
from db import get_conn

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

last_call = {}


def load_memory(uid):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (uid,)
    )

    rows = cur.fetchall()
    conn.close()

    msgs = [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    if not msgs:
        msgs = [{"role": "system", "content": "Bạn là AI Telegram thông minh."}]

    return msgs


def save(uid, role, content):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages(user_id, role, content) VALUES (?, ?, ?)",
        (uid, role, content)
    )

    conn.commit()
    conn.close()


async def ask_ai(uid, text):
    now = time.time()

    if uid in last_call and now - last_call[uid] < 1:
        return "⏳ chậm chút..."

    last_call[uid] = now

    msgs = load_memory(uid)
    msgs.append({"role": "user", "content": text})

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=msgs
    )

    reply = res.choices[0].message.content

    save(uid, "user", text)
    save(uid, "assistant", reply)

    return reply
