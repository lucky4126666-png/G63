import os
import asyncio
import logging

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

import uvicorn
from dotenv import load_dotenv

from ai_service import ask_ai

# ===== ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ===== HANDLER =====
@dp.message()
async def handler(msg: types.Message):
    if not msg.text:
        return

    text = msg.text.strip()
    uid = msg.from_user.id

    # ===== GROUP FILTER =====
    if msg.chat.type != "private":
        if "ai" not in text.lower() and not msg.reply_to_message:
            return

    # ===== AI CHAT =====
    if text.startswith("ai ") or msg.chat.type != "private":
        clean = text.replace("ai ", "")
        reply = await ask_ai(uid, clean)
        return await msg.reply(reply)

# ===== FASTAPI =====
app = FastAPI()

@app.on_event("startup")
async def startup():
    await bot.delete_webhook(drop_pending_updates=True)

    webhook_url = os.getenv("BASE_URL", "") + "/webhook"
    if webhook_url:
        await bot.set_webhook(webhook_url)

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
def home():
    return {"status": "AI bot running"}

# ===== RUN =====
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
