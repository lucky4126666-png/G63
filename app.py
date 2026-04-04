import os
import psycopg2
from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, Update
from aiogram.filters import Command
from dotenv import load_dotenv

# ===== LOAD ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DB_URL = os.getenv("DATABASE_URL")

if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

PORT = int(os.getenv("PORT", 8080))

# ===== INIT BOT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ===== DB CONNECT =====
def connect_db():
    return psycopg2.connect(DB_URL, sslmode="require")

# ===== SAVE USER =====
def save_user(telegram_id, username):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (telegram_id, username)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO NOTHING;
    """, (telegram_id, username))

    conn.commit()
    cur.close()
    conn.close()

# ===== HANDLER =====
@router.message(Command("start"))
async def start_handler(msg: Message):
    print("USER HIT /start")

    save_user(msg.from_user.id, msg.from_user.username)

    await msg.answer("Bot đang hoạt động 🚀")

# ===== REGISTER ROUTER =====
dp.include_router(router)

# ===== WEBHOOK HANDLER =====
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print("ERROR:", e)

    return web.Response()

# ===== HEALTH CHECK =====
async def index(request):
    return web.Response(text="Bot is running 🚀")

# ===== STARTUP =====
async def on_startup(app):
    print("🔥 STARTING SERVER...")

    webhook = f"{WEBHOOK_URL}/webhook"
    await bot.set_webhook(webhook)

    print("✅ Webhook set:", webhook)

# ===== SHUTDOWN (FIX LỖI CRASH) =====
async def on_shutdown(app):
    print("🛑 Shutting down...")
    await bot.session.close()

# ===== MAIN APP =====
def main():
    app = web.Application()

    app.router.add_get("/", index)
    app.router.add_post("/webhook", handle_webhook)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)  # 👈 QUAN TRỌNG

    web.run_app(app, host="0.0.0.0", port=PORT)

# ===== RUN =====
if __name__ == "__main__":
    main()
