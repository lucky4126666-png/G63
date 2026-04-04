import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ===== CONFIG (RAM) =====
CONFIG = {
    "welcome_text": "Bot chạy OK rồi 🚀"
}

# ===== BOT =====
@router.message(Command("start"))
async def start(msg: Message):
    text = CONFIG.get("welcome_text", "Hello")
    await msg.answer(text)

dp.include_router(router)

# ===== WEB ADMIN =====
async def admin_page(request):
    return web.Response(text=f"""
    <html>
    <body>
        <h2>Admin Bot</h2>
        <form method="post" action="/save">
            <label>Welcome Text:</label><br>
            <input name="text" value="{CONFIG['welcome_text']}" style="width:300px"><br><br>
            <button type="submit">Save</button>
        </form>
    </body>
    </html>
    """, content_type='text/html')

async def save_config(request):
    data = await request.post()
    CONFIG["welcome_text"] = data.get("text", "Hello")
    return web.Response(text="✅ Saved! Bot updated instantly.")

# ===== MAIN =====
async def main():
    print("🔥 BOT + WEB RUNNING...")

    app = web.Application()
    app.router.add_get("/admin", admin_page)
    app.router.add_post("/save", save_config)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
