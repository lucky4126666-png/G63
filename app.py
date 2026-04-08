import asyncio
import logging
import sqlite3

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import uvicorn

from config import BOT_TOKEN, BASE_URL, PORT, ADMIN_ID
from db import init_db, get_conn

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ===== CACHE =====
KEYWORDS = {}

def load_keywords():
    global KEYWORDS
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT trigger, response FROM keywords")
    data = cur.fetchall()
    conn.close()
    KEYWORDS = {k: v for k, v in data}
    print("🔥 Loaded", len(KEYWORDS), "keywords")

def add_keyword(trigger, response):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO keywords (trigger, response) VALUES (?,?)",
        (trigger, response)
    )
    conn.commit()
    conn.close()
    load_keywords()

def delete_keyword(trigger):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM keywords WHERE trigger=?", (trigger,))
    conn.commit()
    conn.close()
    load_keywords()

# ===== FSM =====
class AdminState(StatesGroup):
    key = State()
    value = State()
    delete = State()

# ===== MENU =====
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Thêm keyword", callback_data="add")],
        [InlineKeyboardButton(text="📋 Danh sách", callback_data="list")],
        [InlineKeyboardButton(text="🗑️ Xoá keyword", callback_data="delete")],
    ])

# ===== HANDLER =====
@dp.message()
if text.startswith("ai "):
    from ai_service import ask_ai
    reply = await ask_ai(text)
    return await msg.reply(reply)
    
    text = msg.text.strip()
    uid = msg.from_user.id

    if text == "/admin":
        if uid != ADMIN_ID:
            return await msg.answer("❌ No permission")
        return await msg.answer("⚙️ ADMIN", reply_markup=menu())

    current = await state.get_state()

    if current == AdminState.key:
        await state.update_data(key=text)
        await msg.answer("👉 Nhập nội dung:")
        return await state.set_state(AdminState.value)

    if current == AdminState.value:
        data = await state.get_data()
        add_keyword(data["key"].lower(), text)
        await msg.answer("✅ Added")
        return await state.clear()

    if current == AdminState.delete:
        delete_keyword(text)
        await msg.answer("🗑️ Deleted")
        return await state.clear()

    if text.startswith("/"):
        return

    text_lower = text.lower()

    for k, v in KEYWORDS.items():
        if k in text_lower:
            return await msg.reply(v)

    # anti spam
    import re

if re.search(r"(http|t\.me|www|\.com|\.xyz|\.top)", text_lower):
    try:
        await msg.delete()
    except:
        pass

# ===== CALLBACK =====
@dp.callback_query()
async def callback(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return

    if cb.data == "add":
        await cb.message.answer("👉 Nhập KEY:")
        await state.set_state(AdminState.key)

    elif cb.data == "list":
        text = "\n".join([f"{k} → {v}" for k, v in KEYWORDS.items()])
        await cb.message.answer(text or "Empty")

    elif cb.data == "delete":
        await cb.message.answer("👉 Nhập key:")
        await state.set_state(AdminState.delete)

# ===== FASTAPI =====
app = FastAPI()

@app.on_event("startup")
async def startup():
    init_db()
    load_keywords()

    webhook_url = f"{BASE_URL}/webhook"
    await bot.set_webhook(webhook_url)
    print("✅ Webhook set:", webhook_url)

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
def home():
    return {"status": "webhook running"}

@app.post("/send")
async def send_msg(data: dict):
    await bot.send_message(data["chat_id"], data["text"])
    return {"ok": True}
    
# ===== RUN =====
import os

PORT = int(os.getenv("PORT", 8080))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
