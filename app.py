import os, asyncio, requests
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
import psycopg2
import pathlib

# ===== ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
DB_URL = os.getenv("DATABASE_URL")

# ===== BOT =====
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== DB =====
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

def query(q, v=None):
    cur.execute(q, v or ())
    conn.commit()
    return cur.fetchall() if cur.description else None

# ===== AI =====
def ai_detect(text):
    bad = ["airdrop","free","赚"]
    return any(w in text for w in bad)

# ===== BOT HANDLER =====
@dp.message()
async def handler(m: types.Message):
    text = (m.text or "").lower()
    uid = m.from_user.id

    # save user
    query("INSERT INTO users(id) VALUES(%s) ON CONFLICT DO NOTHING",(uid,))

    # AI ban
    if ai_detect(text):
        await m.delete()
        await bot.ban_chat_member(m.chat.id, uid)

# ===== WEBHOOK =====
async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")

# ===== API =====
async def users(request):
    return web.json_response(query("SELECT * FROM users"))

async def groups(request):
    return web.json_response(query("SELECT * FROM groups"))

# ===== MAIN =====
async def main():

    await bot.set_webhook(f"{BASE_URL}/{BOT_TOKEN}")

    app = web.Application()

    # ===== STATIC (React build) =====
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

    print("🚀 SERVER RUNNING")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
