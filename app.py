from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
BASE_URL = os.getenv("BASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message()
async def handler(msg: types.Message):
    if not msg.text:
        return
    await msg.reply("🔥 Bot OK")

app = FastAPI()

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
def home():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(BASE_URL + "/webhook")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
