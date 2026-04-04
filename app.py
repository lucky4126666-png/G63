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

# Fix postgres:// -> postgresql://
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

PORT = int(os.getenv("PORT", 8080))

# ===== INIT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ===== DB =====
def connect_db():
    try:
        conn = psycopg2.connect(DB_URL, sslmode="require")
        print("✅ DB Connected")
        return conn
    except Exception as e:
        print("❌ DB ERROR:", e)
        raise

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
    print("👤 USER:", msg.from_user.id)

    save_user(msg.from_user.id, msg.from_user.username)

    await msg.answer("Bot đang hoạt động 🚀")

dp.include_router(router)

# ===== WEBHOOK =====
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print("❌ WEBHOOK ERROR:", e)

    return web.Response()

# ===== ROUTES =====
async def index(request):
    return web.Response(text="Bot is running 🚀")

# ===== STARTUP =====
async def on_startup(app):
    print("🔥 STARTING SERVER...")

    if not WEBHOOK_URL:
        raise ValueError("❌ WEBHOOK_URL chưa set")

    webhook = f"{WEBHOOK_URL}/webhook"

    await bot.set_webhook(webhook)

    print("✅ Webhook:", webhook)

# ===== SHUTDOWN =====
async def on_shutdown(app):
    print("🛑 Shutdown...")
    await bot.session.close()

# ===== MAIN =====
def main():
    app = web.Application()

    app.router.add_get("/", index)
    app.router.add_post("/webhook", handle_webhook)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host="0.0.0.0", port=PORT)

# ===== RUN =====
if __name__ == "__main__":
    main()
