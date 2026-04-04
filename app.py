import os
import asyncio
import time
import pathlib
import psycopg2
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
from openai import OpenAI

# ===== ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
DB_URL = os.getenv("DATABASE_URL")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

print("DB_URL =", DB_URL[:30] + "..." if DB_URL else "None")

client = OpenAI(api_key=OPENAI_KEY)

# ===== DB CONNECT =====
def connect_db():
    for i in range(10):
        try:
            return psycopg2.connect(DB_URL, sslmode="require")
        except Exception as e:
            print("DB retry...", e)
            time.sleep(2)
    raise Exception("DB connect failed")

# ===== QUERY =====
def query(q, v=None):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(q, v or ())
    conn.commit()
    res = cur.fetchall() if cur.description else None
    cur.close()
    conn.close()
    return res

# ===== INIT DB =====
def init_db():
    query("""
    CREATE TABLE IF NOT EXISTS users (
        id BIGINT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    query("""
    CREATE TABLE IF NOT EXISTS groups (
        id BIGINT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    query("""
    CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        action TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

# ===== BOT =====
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ===== FILTER =====
def is_scam(text):
    text = text.lower()
    bad = ["http", "t.me", "airdrop", "free", "bonus", "click"]
    return any(x in text for x in bad)

# ===== RATE LIMIT =====
last_msg = {}

def is_spam(uid):
    now = time.time()
    if uid in last_msg and now - last_msg[uid] < 1:
        return True
    last_msg[uid] = now
    return False

# ===== AI CHAT =====
async def ai_reply(text):
    try:
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": text}]
        )
        return res.choices[0].message.content
    except Exception as e:
        print("AI error:", e)
        return "⚠️ AI error"

# ===== HANDLER =====
@dp.message()
async def handler(m: types.Message):
    uid = m.from_user.id
    gid = m.chat.id
    text = m.text or ""

    # save user
    try:
        query("INSERT INTO users(id) VALUES(%s) ON CONFLICT DO NOTHING", (uid,))
    except Exception as e:
        print("User save error:", e)

    # save group
    if m.chat.type != "private":
        try:
            query(
                "INSERT INTO groups(id,title) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (gid, m.chat.title)
            )
        except Exception as e:
            print("Group save error:", e)

    # spam
    if is_spam(uid):
        try:
            await m.delete()
        except:
            pass
        return

    # scam
    if is_scam(text):
        try:
            await m.delete()
            await bot.ban_chat_member(gid, uid)
            query("INSERT INTO logs(user_id,action) VALUES(%s,%s)", (uid, "ban_auto"))
        except Exception as e:
            print("Ban error:", e)
        return

    # AI reply private
    if m.chat.type == "private":
        reply = await ai_reply(text)
        await m.answer(reply)

# ===== WEBHOOK =====
async def webhook(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print("Webhook error:", e)
    return web.Response(text="OK")

# ===== API =====
async def api_users(request):
    return web.json_response(query("SELECT * FROM users"))

async def api_groups(request):
    return web.json_response(query("SELECT * FROM groups"))

async def api_logs(request):
    return web.json_response(query("SELECT * FROM logs ORDER BY id DESC LIMIT 50"))

async def api_stats(request):
    users = query("SELECT COUNT(*) FROM users")[0][0]
    groups = query("SELECT COUNT(*) FROM groups")[0][0]
    logs = query("SELECT COUNT(*) FROM logs")[0][0]
    return web.json_response({
        "users": users,
        "groups": groups,
        "logs": logs
    })

# ===== ADMIN =====
async def ban_user(request):
    data = await request.json()
    uid = data.get("user_id")
    gid = data.get("group_id")

    await bot.ban_chat_member(gid, uid)
    query("INSERT INTO logs(user_id,action) VALUES(%s,%s)", (uid, "ban_manual"))

    return web.json_response({"status": "banned"})

async def unban_user(request):
    data = await request.json()
    uid = data.get("user_id")
    gid = data.get("group_id")

    await bot.unban_chat_member(gid, uid)
    query("INSERT INTO logs(user_id,action) VALUES(%s,%s)", (uid, "unban"))

    return web.json_response({"status": "unbanned"})

# ===== MAIN =====
async def main():
    print("🔥 STARTING GOD SERVER")

    init_db()

    try:
        await bot.set_webhook(f"{BASE_URL}/{BOT_TOKEN}")
        print("✅ Webhook set")
    except Exception as e:
        print("Webhook error:", e)

    app = web.Application()

    # ===== STATIC SAFE =====
    STATIC = pathlib.Path("frontend/build")
    if STATIC.exists():
        async def index(request):
            return web.FileResponse(STATIC / "index.html")

        app.router.add_get("/", index)
        app.router.add_static("/", STATIC)
    else:
        print("⚠️ No frontend/build → skip UI")

    # ===== ROUTES =====
    app.router.add_post(f"/{BOT_TOKEN}", webhook)
    app.router.add_get("/api/users", api_users)
    app.router.add_get("/api/groups", api_groups)
    app.router.add_get("/api/logs", api_logs)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_post("/api/ban", ban_user)
    app.router.add_post("/api/unban", unban_user)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)

    await site.start()

    print(f"🚀 RUNNING PORT {port}")

    while True:
        await asyncio.sleep(3600)

# ===== START =====
if __name__ == "__main__":
    asyncio.run(main())
