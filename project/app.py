import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = "8595583672:AAGqM7EnDeTRiKEHZxQpZGIETYvHhX-NKxc"
OPENAI_KEY = "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"

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_KEY)

# ===== HANDLER =====
@dp.message()
async def chat(message: types.Message):
    try:
        await message.answer("🤖 đang suy nghĩ...")

        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "user", "content": message.text}
            ]
        )

        reply = res.choices[0].message.content

        await message.answer(reply)

    except Exception as e:
        await message.answer(f"❌ lỗi: {e}")

# ===== MAIN =====
async def main():
    print("🔥 BOT ĐANG CHẠY...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
