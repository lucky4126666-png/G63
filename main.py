import os
import asyncio
import logging
import psycopg2

from fastapi import FastAPI
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

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

def add_keyword_db(trigger, response):
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

# ===== ADMIN =====
ADMIN_IDS = [8655755346]

def is_admin(uid):
    return uid in ADMIN_IDS

# ===== BOT + STORAGE =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())  # 🔥 FIX FSM

# ===== FSM =====
class AdminState(StatesGroup):
    key = State()
    value = State()
    delete = State()

# ===== MENU =====
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Thêm", callback_data="add")],
        [InlineKeyboardButton(text="📋 Danh sách", callback_data="list")],
        [InlineKeyboardButton(text="🗑️ Xoá", callback_data="delete")],
        [InlineKeyboardButton(text="📊 Stats", callback_data="stats")]
    ])

# ===== START =====
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer("🤖 Bot đang hoạt động")

# ===== ADMIN MENU =====
@dp.message(Command("admin"))
async def admin(msg: Message):
    print("ADMIN HIT:", msg.from_user.id)

    if not is_admin(msg.from_user.id):
        return await msg.answer(f"❌ Không có quyền\nID: {msg.from_user.id}")

    await msg.answer("⚙️ ADMIN PANEL", reply_markup=menu())

# ===== CALLBACK =====
@dp.callback_query(lambda c: c.data in ["add", "list", "delete", "stats"])
async def menu_handler(cb: CallbackQuery, state: FSMContext):

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
        await cb.message.answer(f"📊 Tổng: {len(KEYWORDS_CACHE)}")

# ===== ADD FLOW =====
@dp.message(AdminState.key)
async def get_key(msg: Message, state: FSMContext):
    await state.update_data(key=msg.text)
    await msg.answer("👉 Nhập nội dung:")
    await state.set_state(AdminState.value)

@dp.message(AdminState.value)
async def get_value(msg: Message, state: FSMContext):
    data = await state.get_data()
    add_keyword_db(data["key"].lower(), msg.text)
    await msg.answer("✅ Đã thêm")
    await state.clear()

# ===== DELETE =====
@dp.message(AdminState.delete)
async def delete(msg: Message, state: FSMContext):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM keywords WHERE trigger=%s", (msg.text,))
    conn.commit()
    conn.close()

    load_keywords()
    await msg.answer("🗑️ Đã xoá")
    await state.clear()

# ===== AUTO REPLY =====
@dp.message()
async def auto(msg: Message):
    if not msg.text:
        return

    # 🔥 FIX: không chặn command nữa
    if msg.text.startswith("/"):
        return

    text = msg.text.lower()

    for k, v in KEYWORDS_CACHE.items():
        if k in text:
            return await msg.reply(v)

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
    await bot.delete_webhook(drop_pending_updates=True)  # 🔥 FIX conflict

    bot_task = asyncio.create_task(dp.start_polling(bot))

    port = int(os.environ.get("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)

    api_task = asyncio.create_task(server.serve())

    await asyncio.gather(bot_task, api_task)

if __name__ == "__main__":
    asyncio.run(main())
