import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv

# ===== LOAD ENV =====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ===== LOG =====
logging.basicConfig(level=logging.INFO)

# ===== BOT =====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== KEYWORD DATA =====
KEYWORDS = {
    "hello": "你好 👋",
    "hi": "嗨嗨 😆",
    "giá": "Inbox admin để biết giá 💰",
    "link": "⚠️ Không được gửi link!"
}

# ===== START =====
@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer("🤖 Bot Trung Quốc đã online!")

# ===== AUTO REPLY =====
@dp.message()
async def auto_reply(message: Message):
    text = message.text.lower()

    for key in KEYWORDS:
        if key in text:
            await message.reply(KEYWORDS[key])
            break

    # ===== CHỐNG LINK =====
    if "http" in text or "t.me" in text:
        try:
            await message.delete()
            await message.answer(f"🚫 {message.from_user.full_name} bị xoá tin nhắn vì gửi link!")
        except:
            pass

# ===== MAIN =====
async def main():
    print("🚀 Bot đang chạy...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
