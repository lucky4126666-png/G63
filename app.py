import asyncio
import logging
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import uvicorn

from config import BOT_TOKEN, PORT, ADMIN_ID
from db import init_db, get_conn, release_conn

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
    release_conn(conn)

    KEYWORDS = {k: v for k, v in data}
    logging.info(f"🔥 Loaded {len(KEYWORDS)} keywords")

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
    release_conn(conn)
    load_keywords()

def delete_keyword(trigger):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM keywords WHERE trigger=%s", (trigger,))
    conn.commit()
    release_conn(conn)
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
        [InlineKeyboardButton(text="📊 Stats", callback_data="stats")]
    ])

# ===== ROUTER =====
@dp.message()
async def handler(msg: Message, state: FSMContext):
    if not msg.text:
        return

    text = msg.text.strip()
    uid = msg.from_user.id

    # ADMIN PANEL
    if text == "/admin":
        if uid != ADMIN_ID:
            return await msg.answer("❌ No permission")
        return await msg.answer("⚙️ ADMIN PANEL", reply_markup=menu())

    # FSM FLOW
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

    # AUTO REPLY
    if text.startswith("/"):
        return

    text_lower = text.lower()

    for k, v in KEYWORDS.items():
        if k in text_lower:
            return await msg.reply(v)

    # ANTI SPAM
    if any(x in text_lower for x in ["http", "t.me", ".com", "www"]):
        try:
            await msg.delete()
        except:
            pass

# ===== CALLBACK =====
@dp.callback_query()
async def callback(cb: CallbackQuery, state: FSMContext):
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

    elif cb.data == "stats":
        await cb.message.answer(f"📊 {len(KEYWORDS)} keywords")

# ===== FASTAPI =====
app = FastAPI()

@app.on_event("startup")
async def startup():
    init_db()
    load_keywords()
    asyncio.create_task(dp.start_polling(bot))

@app.get("/")
def home():
    return {"status": "running"}

# ===== RUN =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
