import os
import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ===== BOT =====
@router.message(Command("start"))
async def start(msg: Message):
    await msg.answer("Bot chạy ổn định 🚀")

dp.include_router(router)

# ===== MAIN =====
async def main():
    print("🔥 BOT RUNNING...")

    # ❗ DÒNG QUAN TRỌNG NHẤT (fix conflict vĩnh viễn)
    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
