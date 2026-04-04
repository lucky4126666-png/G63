import asyncio
from aiogram import Bot, Dispatcher
from bot.handlers import register_handlers

bots = {}

async def run_bot(token):
    while True:
        try:
            bot = Bot(token)
            dp = Dispatcher()

            register_handlers(dp)

            print(f"🤖 RUNNING: {token[:8]}")

            await dp.start_polling(bot)

        except Exception as e:
            print(f"🔥 CRASH: {e}")
            await asyncio.sleep(3)


async def start_bot(token):
    if token in bots:
        return

    task = asyncio.create_task(run_bot(token))
    bots[token] = task


async def load_all_bots():
    from core.db import pool

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT token FROM bots WHERE is_active=TRUE")

        for r in rows:
            await start_bot(r["token"])
