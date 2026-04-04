from aiogram import types
from core.db import pool
from core.security import is_spam
from core.ai import ai_reply

def register_handlers(dp):

    @dp.message()
    async def main(message: types.Message):
        uid = message.from_user.id
        text = message.text.lower()

        # 🚫 spam
        if is_spam(uid):
            return await message.answer("🚫 Spam → mute 60s")

        # keyword
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT response FROM keywords WHERE keyword=$1",
                text
            )

        if row:
            return await message.answer(row["response"])

        # 🤖 AI fallback
        reply = await ai_reply(text)
        if reply:
            await message.answer(reply)
