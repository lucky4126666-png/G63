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

def get_keywords():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT trigger, response FROM keywords")
    data = cur.fetchall()
    conn.close()
    return {k: v for k, v in data}

def add_keyword_db(trigger, response):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO keywords (trigger, response) VALUES (%s, %s) ON CONFLICT (trigger) DO UPDATE SET response = EXCLUDED.response",
        (trigger, response)
    )
    conn.commit()
    conn.close()

# ===== BOT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("🤖 Bot full system đang chạy!")

@dp.message()
async def auto_reply(message: Message):
    if not message.text:
        return

    text = message.text.lower()
    keywords = get_keywords()

    for key, response in keywords.items():
        if key in text:
            await message.reply(response)
            return

    # anti link
    if "http" in text or "t.me" in text:
        try:
            await message.delete()
        except:
            pass

# ===== FASTAPI =====
app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/add")
def add(trigger: str, response: str):
    add_keyword_db(trigger, response)
    return {"msg": "added"}

# ===== RUN =====
async def run_bot():
    await dp.start_polling(bot)

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    run_api()
