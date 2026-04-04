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
        text TEXT,
        file_id TEXT,
        file_type TEXT
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
    cur.execute("SELECT trigger, text, file_id, file_type FROM keywords")
    data = cur.fetchall()
    conn.close()

    KEYWORDS_CACHE = {
        k: {
            "text": t,
            "file_id": f,
            "type": tp
        }
        for k, t, f, tp in data
    }

# ===== SAVE =====
def save_keyword(trigger, text=None, file_id=None, file_type=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO keywords (trigger, text, file_id, file_type)
    VALUES (%s,%s,%s,%s)
    ON CONFLICT (trigger)
    DO UPDATE SET text=%s, file_id=%s, file_type=%s
    """, (trigger, text, file_id, file_type, text, file_id, file_type))
    conn.commit()
    conn.close()
    load_keywords()

# ===== DELETE =====
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
    waiting_key = State()
    waiting_content = State()

# ===== MENU =====
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Thêm", callback_data="add")],
        [InlineKeyboardButton(text="📋 List", callback_data="list")]
    ])

# ===== ADMIN =====
@dp.message()
async def router(msg: Message, state: FSMContext):
    if not msg.text and not msg.photo and not msg.video and not msg.animation:
        return

    # ===== ADMIN MENU =====
    if msg.text == "/admin":
        if not is_admin(msg.from_user.id):
            return
        return await msg.answer("⚙️ ADMIN PANEL", reply_markup=menu())

    # ===== FSM =====
    current = await state.get_state()

    if current == AdminState.waiting_key:
        await state.update_data(key=msg.text.lower())
        await msg.answer("👉 Gửi nội dung (text / ảnh / video / gif):")
        return await state.set_state(AdminState.waiting_content)

    if current == AdminState.waiting_content:
        data = await state.get_data()
        key = data["key"]

        text = msg.caption if msg.caption else msg.text

        file_id = None
        file_type = None

        if msg.photo:
            file_id = msg.photo[-1].file_id
            file_type = "photo"

        elif msg.video:
            file_id = msg.video.file_id
            file_type = "video"

        elif msg.animation:
            file_id = msg.animation.file_id
            file_type = "gif"

        save_keyword(key, text, file_id, file_type)

        await msg.answer(f"✅ Đã lưu: {key}")
        return await state.clear()

    # ===== AUTO REPLY =====
    if msg.text and not msg.text.startswith("/"):
        text = msg.text.lower()

        for k, data in KEYWORDS_CACHE.items():
            if k in text:

                if data["type"] == "photo":
                    return await msg.answer_photo(
                        data["file_id"],
                        caption=data["text"],
                        parse_mode="HTML"
                    )

                if data["type"] == "video":
                    return await msg.answer_video(
                        data["file_id"],
                        caption=data["text"],
                        parse_mode="HTML"
                    )

                if data["type"] == "gif":
                    return await msg.answer_animation(
                        data["file_id"],
                        caption=data["text"],
                        parse_mode="HTML"
                    )

                return await msg.answer(data["text"], parse_mode="HTML")

# ===== CALLBACK =====
@dp.callback_query()
async def callback(cb: CallbackQuery, state: FSMContext):

    if not is_admin(cb.from_user.id):
        return

    if cb.data == "add":
        await cb.message.answer("👉 Nhập keyword:")
        await state.set_state(AdminState.waiting_key)

    elif cb.data == "list":
        for k in KEYWORDS_CACHE:
            await cb.message.answer(k)

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
