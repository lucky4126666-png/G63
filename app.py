import os
import asyncio
import time
import pathlib
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
import psycopg2

# ===== LOAD ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
DB_URL = os.getenv("DATABASE_URL")

print("DB_URL =", DB_URL)

# ===== BOT =====
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== DB CONNECT (retry) =====
def connect_db():
    for i in range(10):
        try:
            print("🔌 Connecting DB...")
            conn = psycopg2.connect(DB_URL)
            print("✅ DB Connected")
            return conn
        except Exception as e:
            print("❌ DB fail, retry...", e)
            time.sleep(2)
    raise Exception("DB connect failed")

conn = connect_db()
cur = conn.cursor()

# ===== QUERY =====
def query(q, v=None):
    cur.execute(q, v or ())
    conn.commit()
    if cur.description:
        return cur.fetchall()
    return None

# ===== AI FILTER =====
def ai_detect(text):
    bad = ["airdrop", "free", "赚"]
    return any(w in text for w in bad)

# ===== BOT HANDLER =====
@dp.message()
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


from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def start(msg: Message):
    save_user(msg.from_user.id, msg.from_user.username)
    await msg.answer("Bot đang hoạt động 🚀")
    
    # save user
    query("INSERT INTO users(id) VALUES(%s) ON CONFLICT DO NOTHING", (uid,))

    # detect scam
    if ai_detect(text):
        try:
            await m.delete()
            await bot.ban_chat_member(m.chat.id, uid)
        except:
            pass

# ===== WEBHOOK =====
async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")

# ===== API =====
async def users(request):
    return web.json_response(query("SELECT * FROM users") or [])

async def groups(request):
    return web.json_response(query("SELECT * FROM groups") or [])

# ===== MAIN =====
async def main():
    # set webhook
    await bot.set_webhook(f"{BASE_URL}/{BOT_TOKEN}")
    print("✅ Webhook set")

    app = web.Application()

    # ===== STATIC =====
    STATIC = pathlib.Path("frontend/build")

    if STATIC.exists():
        async def index(request):
            return web.FileResponse(STATIC / "index.html")

        app.router.add_get("/", index)
        app.router.add_static("/", STATIC)

    # ===== ROUTES =====
    app.router.add_post(f"/{BOT_TOKEN}", handle)
    app.router.add_get("/api/users", users)
    app.router.add_get("/api/groups", groups)

    # ===== RUN SERVER =====
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)

    await site.start()

    print("🚀 SERVER RUNNING on port", port)

    while True:
        await asyncio.sleep(3600)

# ===== START =====
if __name__ == "__main__":
    print("🔥 STARTING SERVER...")
    asyncio.run(main())
