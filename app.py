import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import uvicorn

from db import init_db
from ai_service import ask_ai

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

init_db()

# ===== BOT =====
@dp.message()
async def handler(msg: types.Message):
    if not msg.text:
        return

    text = msg.text.strip()
    uid = msg.from_user.id

    if msg.chat.type != "private":
        if "ai" not in text.lower() and not msg.reply_to_message:
            return

    if text.startswith("ai ") or msg.chat.type != "private":
        clean = text.replace("ai ", "")
        reply = await ask_ai(uid, clean)
        await msg.reply(reply)

# ===== FASTAPI =====
app = FastAPI()

@app.on_event("startup")
async def startup():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(BASE_URL + "/webhook")

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# ===== DASHBOARD =====
@app.get("/dashboard")
def dashboard():
    return """
    <h1>🚀 AI SaaS Dashboard</h1>
    <p>Bot đang chạy OK</p>
    <p>/webhook active</p>
    """

@app.get("/")
def home():
    return {"status": "running"}

# ===== RUN =====
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
