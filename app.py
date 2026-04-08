import os
import re
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import uvicorn

from db import init_db, get_setting, set_setting
from ai_service import ask_ai

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", 8080))

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(link_preview_is_disabled=True)
)

dp = Dispatcher(storage=MemoryStorage())
init_db()

# ================= START =================
@dp.message(lambda m: m.text == "/start")
async def start(m: types.Message):
    if m.chat.type != "private":
        return

    text = get_setting("start_text") or (
        "点击此处可以添加机器人进群\n"
        "http://t.me/xbqgk?startgroup=foo\n\n"
        "更多服务，请访问 https://t.me/xbkf/"
    )

    await m.answer(text)


# ================= BOT JOIN =================
@dp.my_chat_member()
async def bot_join(e: types.ChatMemberUpdated):
    if e.new_chat_member.status in ("member", "administrator"):
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="公群导航", url="https://t.me/xbkf"),
            InlineKeyboardButton(text="供需频道", url="https://t.me/xbkf")
        ]])

        await bot.send_message(
            e.chat.id,
            "N组防骗助手为您服务,我正在进行相关初始化配置请稍后",
            reply_markup=kb
        )


# ================= USER JOIN =================
@dp.message(lambda m: m.new_chat_members)
async def welcome(m: types.Message):
    chat = m.chat
    group_name = chat.title

    for u in m.new_chat_members:
        text = f"""欢迎 {u.full_name} 来到
{group_name}

交易前请先关注担保流程【@xinb】

⚠️注意：主动私聊你的都是骗子！
"""

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="新币供需", url="https://t.me/xbkf"),
            InlineKeyboardButton(text="新币公群", url="https://t.me/xbkf")
        ]])

        await m.answer(text, reply_markup=kb)

        # ===== ADMIN CHECK =====
        admins = await bot.get_chat_administrators(chat.id)
        ids = [a.user.id for a in admins]

        if not any(i in ids for i in ADMIN_IDS):
            await m.answer(
                "⚠️ 风险提示，本群没有检测到新币管理员。\n"
                "有交易风险，请联系 @xbkf"
            )


# ================= ANTI SCAM =================
@dp.message()
async def anti_scam(m: types.Message):
    if not m.text:
        return

    text = m.text.lower()

    # link spam
    if re.search(r"(http|t.me|www|\.com)", text):
        try:
            await m.delete()
        except:
            pass

    # keyword scam
    if any(x in text for x in ["私聊", "转账", "usdt", "担保"]):
        await m.reply("⚠️ 疑似诈骗，请注意安全")


# ================= AI =================
@dp.message()
async def ai_handler(m: types.Message):
    if not m.text:
        return

    if m.chat.type != "private" and "ai" not in m.text.lower():
        return

    reply = await ask_ai(m.from_user.id, m.text.replace("ai ", ""))
    await m.reply(reply)


# ================= DASHBOARD =================
@app.get("/admin", response_class=HTMLResponse)
def admin():
    return open("dashboard.html", encoding="utf-8").read()


@app.post("/admin/set")
async def set_text(data: dict):
    set_setting("start_text", data["text"])
    return {"ok": True}


@app.get("/admin/get")
async def get_text():
    return {"text": get_setting("start_text")}


# ================= FASTAPI =================
# ===== FASTAPI =====
app = FastAPI()

# ===== DASHBOARD =====
@app.get("/admin", response_class=HTMLResponse)
def admin():
    return open("dashboard.html", encoding="utf-8").read()


@app.on_event("startup")
async def start_app():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(BASE_URL + "/webhook")


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
def home():
    return {"status": "running"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
