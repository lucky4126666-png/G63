import os
import asyncio
import logging
import psycopg2
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv
import uvicorn

# ===== ENV =====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ===== LOG =====
logging.basicConfig(level=logging.INFO)

# ===== DB =====
def get_conn():
    return psycopg2.connect(DATABASE_URL)

# ===== CACHE (SIÊU QUAN TRỌNG) =====
KEYWORDS_CACHE = {}

def load_keywords():
    global KEYWORDS_CACHE
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT trigger, response FROM keywords")
        data = cur.fetchall()
        conn.close()

        KEYWORDS_CACHE = {k: v for k, v in data}
        print(f"🔥 Loaded {len(KEYWORDS_CACHE)} keywords")

    except Exception as e:
        print("DB ERROR:", e)

def add_keyword_db(trigger, response):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO keywords (trigger, response)
        VALUES (%s, %s)
        ON CONFLICT (trigger)
        DO UPDATE SET response = EXCLUDED.response
        """,
        (trigger, response)
    )
    conn.commit()
    conn.close()

    load_keywords()  # reload cache ngay

# ===== BOT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("🤖 Bot Trung Quốc PRO đã online!")

# ===== AUTO REPLY =====
@dp.message()
async def auto_reply(message: Message):
    try:
        if not message.text:
            return

        text = message.text.lower()

        # ⚡ check keyword từ cache (cực nhanh)
        for key, response in KEYWORDS_CACHE.items():
            if key in text:
                await message.reply(response)
                return

        # 🚫 anti link
        if "http" in text or "t.me" in text:
            await message.delete()
            return

    except Exception as e:
        print("BOT ERROR:", e)

# ===== FASTAPI =====
app = FastAPI()

@app.on_event("startup")
async def startup():
    print("🚀 Server starting...")
    load_keywords()

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/add")
def add(trigger: str, response: str):
    add_keyword_db(trigger, response)
    return {"msg": "added"}

# ===== MAIN (QUAN TRỌNG NHẤT) =====
async def main():
    # 🔥 fix webhook conflict
    await bot.delete_webhook(drop_pending_updates=True)

    # chạy bot + API song song
    bot_task = asyncio.create_task(dp.start_polling(bot))

    config = uvicorn.Config(app, host="0.0.0.0", port=8080)
    server = uvicorn.Server(config)
    api_task = asyncio.create_task(server.serve())

    await asyncio.gather(bot_task, api_task)

if __name__ == "__main__":
    asyncio.run(main())
