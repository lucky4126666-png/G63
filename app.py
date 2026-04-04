import os
import psycopg2
import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ===== DB =====
def connect_db():
    return psycopg2.connect(DB_URL, sslmode="require")

def save_user(user_id, username):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (telegram_id, username)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO NOTHING;
    """, (user_id, username))

    conn.commit()
    cur.close()
    conn.close()

# ===== HANDLER =====
@router.message(Command("start"))
async def start(msg: Message):
    save_user(msg.from_user.id, msg.from_user.username)
    await msg.answer("Bot chạy ngon rồi 🚀")

dp.include_router(router)

# ===== MAIN =====
async def main():
    print("🔥 BOT RUNNING (POLLING)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
