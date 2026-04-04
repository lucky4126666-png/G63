import os
import asyncio
import logging
import psycopg2

from fastapi import FastAPI
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import uvicorn

# ===== ENV =====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

# ===== DB =====
def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS keywords (
        id SERIAL PRIMARY KEY,
        trigger TEXT UNIQUE,
        response TEXT
    );
    """)
    conn.commit()
    conn.close()

# ===== CACHE =====
KEYWORDS_CACHE = {}

def load_keywords():
    global KEYWORDS_CACHE
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT trigger, response FROM keywords")
    data = cur.fetchall()
    conn.close()
    KEYWORDS_CACHE = {k: v for k, v in data}
    print("🔥 Loaded", len(KEYWORDS_CACHE), "keywords")

def add_keyword(trigger, response):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO keywords (trigger, response)
    VALUES (%s,%s)
    ON CONFLICT (trigger)
    DO UPDATE SET response = EXCLUDED.response
    """, (trigger, response))
    conn.commit()
    conn.close()
    load_keywords()

def delete_keyword(trigger):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM keywords WHERE trigger=%s", (trigger,))
    conn.commit()
    conn.close()
    load_keywords()

# ===== ADMIN =====
ADMIN_IDS = [8655755346]

def is_admin(uid):
    return uid in ADMIN_IDS

# ===== BOT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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
        [InlineKeyboardButton(text="📊 Stats", callback_data="stats")]
    ])

# ===== FORCE ADMIN COMMAND (FIX 100%) =====
@dp.message()
async def router(msg: Message, state: FSMContext):
    if not msg.text:
        return

    text = msg.text.strip()

    # ===== ADMIN MENU =====
    if text == "/admin":
        if not is_admin(msg.from_user.id):
            return await msg.answer(f"❌ Không có quyền\nID: {msg.from_user.id}")
        return await msg.answer("⚙️ ADMIN PANEL", reply_markup=menu())

    # ===== FSM FLOW =====
    current = await state.get_state()

    if current == AdminState.key:
        await state.update_data(key=text)
        await msg.answer("👉 Nhập nội dung:")
        return await state.set_state(AdminState.value)

    if current == AdminState.value:
        data = await state.get_data()
        add_keyword(data["key"].lower(), text)
        await msg.answer("✅ Đã thêm")
        return await state.clear()

    if current == AdminState.delete:
        delete_keyword(text)
        await msg.answer("🗑️ Đã xoá")
        return await state.clear()

    # ===== AUTO REPLY =====
    if text.startswith("/"):
        return

    text_lower = text.lower()

    for k, v in KEYWORDS_CACHE.items():
        if k in text_lower:
            return await msg.reply(v)

    # anti link
    if "http" in text_lower or "t.me" in text_lower:
        try:
            await msg.delete()
        except:
            pass

# ===== CALLBACK =====
@dp.callback_query()
async def callback(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return

    if cb.data == "add":
        await cb.message.answer("👉 Nhập KEY:")
        await state.set_state(AdminState.key)

    elif cb.data == "list":
        text = "\n".join([f"{k} → {v}" for k, v in KEYWORDS_CACHE.items()])
        await cb.message.answer(text or "Trống")

    elif cb.data == "delete":
        await cb.message.answer("👉 Nhập key cần xoá:")
        await state.set_state(AdminState.delete)

    elif cb.data == "stats":
        await cb.message.answer(f"📊 Tổng keyword: {len(KEYWORDS_CACHE)}")

# ===== FASTAPI =====
app = FastAPI()

@app.on_event("startup")
async def startup():
    init_db()
    load_keywords()

@app.get("/")
def home():
    return {"status": "ok"}

# ===== MAIN =====
async def main():
    await bot.delete_webhook(drop_pending_updates=True)

    bot_task = asyncio.create_task(dp.start_polling(bot))

    port = int(os.environ.get("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)

    api_task = asyncio.create_task(server.serve())

    await asyncio.gather(bot_task, api_task)

if __name__ == "__main__":
    asyncio.run(main())
