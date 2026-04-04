import os
import asyncio
import time
import pathlib
import psycopg2
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv

# ===== ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
DB_URL = os.getenv("DATABASE_URL")

print("DB_URL =", DB_URL[:30] + "..." if DB_URL else "None")

# ===== DB CONNECT (RETRY + SSL) =====
def connect_db():
    for i in range(10):
        try:
            print("🔌 Connecting DB...")
            return psycopg2.connect(
                DB_URL,
                sslmode="require"   # 👈 bắt buộc Railway
            )
        except Exception as e:
            print("❌ DB fail, retry...", e)
            time.sleep(2)

    raise Exception("DB connect failed")

# ===== QUERY (NO GLOBAL CONNECTION) =====
def query(q, v=None):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute(q, v or ())
    conn.commit()

    result = cur.fetchall() if cur.description else None

    cur.close()
    conn.close()

    return result

# ===== BOT =====
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== AI FILTER =====
def ai_detect(text):
    bad = ["airdrop", "free", "赚"]
    return any(w in text for w in bad)

# ===== BOT HANDLER =====
@dp.message()
async def handler(m: types.Message):
    text = (m.text or "").lower()
    uid = m.from_user.id

    try:
        # save user
        query(
            "INSERT INTO users(id) VALUES(%s) ON CONFLICT DO NOTHING",
            (uid,)
        )
    except Exception as e:
        print("DB insert error:", e)

    # AI ban
    if ai_detect(text):
        try:
            await m.delete()
            await bot.ban_chat_member(m.chat.id, uid)
        except Exception as e:
            print("Ban error:", e)

# ===== WEBHOOK =====
async def handle(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print("Webhook error:", e)

    return web.Response(text="OK")

# ===== API =====
async def users(request):
    try:
        data = query("SELECT * FROM users")
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)})

async def groups(request):
    try:
        data = query("SELECT * FROM groups")
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)})

# ===== MAIN =====
async def main():
    print("🔥 STARTING SERVER...")

    # ===== SET WEBHOOK =====
    try:
        await bot.set_webhook(f"{BASE_URL}/{BOT_TOKEN}")
        print("✅ Webhook set")
    except Exception as e:
        print("❌ Webhook error:", e)

    app = web.Application()

    # ===== STATIC =====
    STATIC = pathlib.Path("frontend/build")

    async def index(request):
        return web.FileResponse(STATIC / "index.html")

    app.router.add_get("/", index)
    app.router.add_static("/", STATIC)

    # ===== ROUTES =====
    app.router.add_post(f"/{BOT_TOKEN}", handle)
    app.router.add_get("/api/users", users)
    app.router.add_get("/api/groups", groups)

    # ===== RUN =====
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)

    await site.start()

    print(f"🚀 SERVER RUNNING ON PORT {port}")

    while True:
        await asyncio.sleep(3600)

# ===== START =====
if __name__ == "__main__":
    asyncio.run(main())
