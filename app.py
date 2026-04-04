import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types

# ===== CONFIG =====
BOT_TOKEN = os.environ["8595583672:AAGqM7EnDeTRiKEHZxQpZGIETYvHhX-NKxc"]  # bắt buộc phải có

# ===== LOG =====
logging.basicConfig(level=logging.INFO)

# ===== INIT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== DATA =====
users = {}

# ===== BOT HANDLER =====
@dp.message()
async def handle(message: types.Message):
    text = message.text.lower()

    if text == "ping":
        await message.answer("pong 🏓")

    elif text.startswith("set "):
        value = text[4:]
        users[message.from_user.id] = value
        await message.answer(f"✅ saved: {value}")

    elif text == "get":
        value = users.get(message.from_user.id, "none")
        await message.answer(f"📦 {value}")

    else:
        await message.answer("🤖 bot running...")

# ===== WEB =====
async def index(request):
    return web.Response(text=f"""
    <h1>🚀 BOT VIP</h1>
    <p>Status: ONLINE</p>
    <p>Users: {len(users)}</p>
    """, content_type="text/html")

app = web.Application()
app.router.add_get("/", index)

# ===== START BOT =====
async def start_bot(app):
    print("🔥 Bot started")
    asyncio.create_task(dp.start_polling(bot))

# ===== CLEANUP =====
async def stop_bot(app):
    print("🛑 Bot stopping")
    await bot.session.close()

# ===== HOOK =====
app.on_startup.append(start_bot)
app.on_cleanup.append(stop_bot)

# ===== RUN =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)
