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

# ===== LOAD ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", 8080))

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# ===== CREATE FASTAPI (PHẢI Ở TRƯỚC) =====
app = FastAPI()

# ===== BOT =====
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(link_preview_is_disabled=True)
)

dp = Dispatcher(storage=MemoryStorage())
init_db()

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

# ================= START =================
@dp.message(lambda m: m.new_chat_members)
async def welcome(m: types.Message):
    chat = m.chat
    group_name = chat.title or "本群"

    for u in m.new_chat_members:
        name = u.full_name

        text = (
            f"欢迎 {name} 来到\n"
            f"{group_name}\n\n"
            "交易前请先关注，担保流程【 @xinb 】\n\n"
            "1.交易前认准群老板和业务员头衔，先看清楚置顶的群规则和报备模版；\n"
            "2.交易前群老板方必须在公群内进行报备，客户确认报备内容，如客户没确认此报备视为无效报备；\n"
            "3.交易过程中有任何变动需要在群内保留记录或者重新报备；\n"
            "4.有任何问题可以联系新币24小时客服 @xbkf\n\n"
            "⚠️注意：主动私聊你的都是骗子！\n"
            "新币所有群（纠纷群、作业群、公群、专群）都由新币担保靓号拉群，\n"
            "一切交易必须群内进行,切勿私下交易,请按照担保流程进行交易。\n\n"
            "此用户是新币尊贵的VIP成员"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="新币供需", url="https://t.me/xbkf"),
                InlineKeyboardButton(text="新币公群", url="https://t.me/xbkf")
            ]
        ])

        await m.answer(text, reply_markup=kb)

        # ===== CHECK ADMIN =====
        admins = await bot.get_chat_administrators(chat.id)
        admin_ids = [a.user.id for a in admins]

        if not any(i in admin_ids for i in ADMIN_IDS):
            await m.answer(
                "⚠️ 风险提示，本群没有检测到新币管理员。\n"
                "有交易风险，请联系 @xbkf"
            )
# ================= USER JOIN =================
@dp.message(lambda m: m.new_chat_members)
async def welcome(m: types.Message):
    chat = m.chat
    group_name = chat.title

    for u in m.new_chat_members:
        text = f"""欢迎 {u.full_name} 来到
{group_name}

⚠️注意：主动私聊你的都是骗子！
"""

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="新币供需", url="https://t.me/xbkf"),
            InlineKeyboardButton(text="新币公群", url="https://t.me/xbkf")
        ]])

        await m.answer(text, reply_markup=kb)

        admins = await bot.get_chat_administrators(chat.id)
        ids = [a.user.id for a in admins]

        if not any(i in ids for i in ADMIN_IDS):
            await m.answer(
                "⚠️ 风险提示，本群没有检测到新币管理员。\n"
                "有交易风险，请联系 @xbkf"
            )

# ================= ANTI SCAM =================
@dp.message()
async def anti(m: types.Message):
    if not m.text:
        return

    text = m.text.lower()

    if re.search(r"(http|t.me|www|\.com)", text):
        try:
            await m.delete()
        except:
            pass

# ================= AI =================
@dp.message()
async def ai(m: types.Message):
    if not m.text:
        return

    if m.chat.type != "private" and "ai" not in m.text.lower():
        return

    reply = await ask_ai(m.from_user.id, m.text.replace("ai ", ""))
    await m.reply(reply)

# ================= WEBHOOK =================
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

# ================= RUN =================
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
