import os
import json
import asyncio
import logging

from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import uvicorn

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [8655755346]

DATA_FILE = "data.json"

logging.basicConfig(level=logging.INFO)

# ===== LOAD DATA =====
KEYWORDS = {}

def load_data():
    global KEYWORDS
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            KEYWORDS = json.load(f)
    except:
        KEYWORDS = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(KEYWORDS, f, ensure_ascii=False, indent=2)

# ===== BOT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def is_admin(uid):
    return uid in ADMIN_IDS

# ===== FSM =====
class Form(StatesGroup):
    key = State()
    content = State()
    edit = State()

# ===== MENU =====
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Thêm", callback_data="add")],
        [InlineKeyboardButton(text="📋 List", callback_data="list")]
    ])

def item_btn(key):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Edit", callback_data=f"edit:{key}"),
            InlineKeyboardButton(text="🗑️ Delete", callback_data=f"del:{key}")
        ]
    ])

# ===== MAIN ROUTER =====
@dp.message()
async def router(msg: Message, state: FSMContext):
    try:
        text = msg.text or msg.caption or ""

        # ===== ADMIN =====
        if text == "/admin":
            if not is_admin(msg.from_user.id):
                return
            return await msg.answer("⚙️ ADMIN PANEL", reply_markup=menu())

        current = await state.get_state()

        # ===== ADD KEY =====
        if current == Form.key:
            await state.update_data(key=text.lower())
            await msg.answer("👉 Gửi nội dung (text/ảnh/video/gif)")
            return await state.set_state(Form.content)

        # ===== SAVE =====
        if current == Form.content:
            data = await state.get_data()

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

            KEYWORDS[data["key"]] = {
                "text": text,
                "file_id": file_id,
                "type": file_type
            }

            save_data()

            await msg.answer("✅ Saved")
            return await state.clear()

        # ===== EDIT =====
        if current == Form.edit:
            data = await state.get_data()
            KEYWORDS[data["edit_key"]]["text"] = text
            save_data()

            await msg.answer("✏️ Updated")
            return await state.clear()

        # ===== AUTO REPLY (STRICT) =====
        if text.startswith("/"):
            return

        key = text.lower().strip()
        data = KEYWORDS.get(key)

        if not data:
            return

        if data["type"] == "photo":
            return await msg.answer_photo(data["file_id"], caption=data["text"], parse_mode="HTML")

        if data["type"] == "video":
            return await msg.answer_video(data["file_id"], caption=data["text"], parse_mode="HTML")

        if data["type"] == "gif":
            return await msg.answer_animation(data["file_id"], caption=data["text"], parse_mode="HTML")

        return await msg.answer(data["text"], parse_mode="HTML")

    except Exception as e:
        print("ERROR:", e)

# ===== CALLBACK =====
@dp.callback_query()
async def cb(cb: CallbackQuery, state: FSMContext):

    if not is_admin(cb.from_user.id):
        return

    if cb.data == "add":
        await cb.message.answer("👉 Nhập keyword:")
        await state.set_state(Form.key)

    elif cb.data == "list":
        for k in KEYWORDS:
            await cb.message.answer(f"🔑 {k}", reply_markup=item_btn(k))

    elif cb.data.startswith("del:"):
        key = cb.data.split(":")[1]
        KEYWORDS.pop(key, None)
        save_data()
        await cb.message.answer(f"🗑️ Deleted {key}")

    elif cb.data.startswith("edit:"):
        key = cb.data.split(":")[1]
        await state.update_data(edit_key=key)
        await cb.message.answer("👉 Nhập nội dung mới:")
        await state.set_state(Form.edit)

# ===== FASTAPI =====
app = FastAPI()

@app.on_event("startup")
async def startup():
    load_data()

@app.get("/")
def home():
    return {"status": "ok"}

# ===== MAIN =====
async def main():
    await bot.delete_webhook(drop_pending_updates=True)

    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print("CRASH:", e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
