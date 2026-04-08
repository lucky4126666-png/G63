import os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import uvicorn

from db import init_db
from ai_service import ask_ai

# ===== LOAD ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", 8080))

if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN missing")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ===== INIT DB =====
init_db()

# ===== START MESSAGE =====
@dp.message(lambda msg: msg.text == "/start")
async def start(msg: types.Message):
    if msg.chat.type != "private":
        return

    text = (
        "点击此处可以添加机器人进群\n"
        "http://t.me/xbqgk?startgroup=foo\n\n"
        "更多服务，请访问 https://t.me/xbkf/"
    )

    await msg.answer(text)


# ===== AI HANDLER =====
@dp.message()
async def handle_message(msg: types.Message):
    if not msg.text:
        return

    text = msg.text.strip()
    user_id = msg.from_user.id

    # group filter
    if msg.chat.type != "private":
        if "ai" not in text.lower() and not msg.reply_to_message:
            return

    if text.startswith("ai ") or msg.chat.type != "private":
        clean = text.replace("ai ", "")
        reply = await ask_ai(user_id, clean)
        await msg.reply(reply)


# ===== FASTAPI =====
app = FastAPI()


@app.on_event("startup")
async def startup():
    await bot.delete_webhook(drop_pending_updates=True)

    if BASE_URL:
        webhook_url = BASE_URL + "/webhook"
        await bot.set_webhook(webhook_url)
        print("✅ Webhook:", webhook_url)


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
def home():
    return {"status": "running"}


@app.get("/dashboard")
def dashboard():
    return """
    <h2>🚀 AI BOT RUNNING</h2>
    <p>Webhook OK</p>
    <p>Memory DB OK</p>
    """


# ===== RUN =====
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
