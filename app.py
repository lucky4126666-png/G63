import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from dotenv import load_dotenv

# ===== LOAD ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ===== LOG =====
logging.basicConfig(level=logging.INFO)

# ===== INIT BOT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== MEMORY DB (simple) =====
users = {}

# ===== BOT COMMAND =====
@dp.message()
async def handle_message(message: Message):
    text = message.text.lower()

    if text == "ping":
        await message.answer("pong 🏓")

    elif text.startswith("set "):
        key = text.replace("set ", "")
        users[message.from_user.id] = key
        await message.answer(f"✅ Đã lưu: {key}")

    elif text == "get":
        val = users.get(message.from_user.id, "chưa có dữ liệu")
        await message.answer(f"📦 Data: {val}")

    else:
        await message.answer("🤖 Bot VIP đang chạy!")

# ===== WEB ADMIN =====
async def index(request):
    html = """
    <html>
    <head><title>BOT VIP</title></head>
    <body style="font-family:sans-serif">
        <h1>🚀 BOT VIP DASHBOARD</h1>
        <p>Status: ONLINE</p>
        <p>Total Users: %d</p>
    </body>
    </html>
    """ % len(users)
    return web.Response(text=html, content_type="text/html")

app = web.Application()
app.router.add_get("/", index)

# ===== MAIN =====
async def start_bot():
    print("🔥 Bot started...")
    await dp.start_polling(bot)

# ===== RUN =====
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # chạy bot song song web
    loop.create_task(start_bot())

    port = int(os.getenv("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)
