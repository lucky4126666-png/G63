import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message

from db import get_conn

BOTS = {}

async def start_bot(bot_id, token):
    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message()
    async def handler(msg: Message):
        text = msg.text.lower()

        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT response FROM keywords WHERE bot_id=%s AND trigger=%s",
            (bot_id, text)
        )

        row = cur.fetchone()
        conn.close()

        if row:
            await msg.answer(row[0])

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
