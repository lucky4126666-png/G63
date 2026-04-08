import os, logging, traceback
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import uvicorn

from db import *

# ===== CONFIG =====
logging.basicConfig(level=logging.INFO)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

init_db()

# ===== BUTTON =====
def build_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="新币供需", url="https://t.me/xbkf"),
            InlineKeyboardButton(text="新币公群", url="https://t.me/xbkf")
        ]
    ])

def build_join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="公群导航", url="https://t.me/xbkf"),
            InlineKeyboardButton(text="供需频道", url="https://t.me/xbkf")
        ]
    ])

# ===== PERMISSION =====
async def is_allowed(chat_id, user_id):
    if get_admin(user_id):
        return True

    admins = await bot.get_chat_administrators(chat_id)
    return any(a.user.id == user_id for a in admins)

# ================= HOME =================
@app.get("/")
def home():
    return {"status": "running"}

# ================= START PRIVATE =================
@dp.message(lambda m: m.text == "/start")
async def start(m: types.Message):
    if m.chat.type != "private":
        return

    await m.answer(
        "点击此处可以添加机器人进群\n"
        "http://t.me/xbqgk?startgroup=foo\n\n"
        "更多服务，请访问 https://t.me/xbkf/"
    )

# ================= BOT JOIN =================
@dp.my_chat_member()
async def bot_join(e: types.ChatMemberUpdated):
    try:
        if e.new_chat_member.user.id != (await bot.me()).id:
            return

        if e.new_chat_member.status not in ("member", "administrator"):
            return

        chat_id = e.chat.id
        save_group(chat_id, e.chat.title)

        # message join
        await bot.send_message(
            chat_id,
            "N组防骗助手为您服务,我正在进行相关初始化配置请稍后",
            reply_markup=build_join_kb()
        )

        # check admin
        admins = await bot.get_chat_administrators(chat_id)
        ids = [a.user.id for a in admins]

        if not any(get_admin(i) for i in ids):
            await bot.send_message(
                chat_id,
                "⚠️ 风险提示，本群没有检测到新币管理员。\n有交易风险，请联系 @xbkf"
            )

    except:
        print(traceback.format_exc())

# ================= USER JOIN =================
@dp.message(lambda m: m.new_chat_members)
async def welcome(m: types.Message):
    try:
        group = m.chat.title or "本群"

        for u in m.new_chat_members:
            if u.is_bot:
                continue

            name = u.full_name

            text = f"""欢迎 {name} 来到
{group}

公群i组1739-供押55888U鼎鑫一手水房/泰国韩国缅甸/一道料直通车公群（月结）

交易前请先关注，担保流程【 @xinb 】

1.交易前认准群老板和业务员头衔；
2.必须在群内报备交易；
3.所有记录必须保留；
4.联系客服 @xbkf

⚠️注意：主动私聊你的都是骗子！
所有交易必须群内进行！

此用户是新币尊贵的VIP成员
"""

            await m.answer(text, reply_markup=build_kb())

    except:
        print(traceback.format_exc())

# ================= LOCK =================
@dp.message(lambda m: m.text in ["下课", "/lock"])
async def lock(m: types.Message):
    if not await is_allowed(m.chat.id, m.from_user.id):
        return

    try:
        await bot.set_chat_permissions(
            m.chat.id,
            types.ChatPermissions(can_send_messages=False)
        )
    except:
        return await m.answer("❌ bot chưa có quyền")

    await m.answer(
        "本公群已下课关闭发言\n如需交易，请恢复后操作！切勿私下交易！！",
        reply_markup=build_kb()
    )

# ================= OPEN =================
@dp.message(lambda m: m.text in ["上课", "/open"])
async def open_group(m: types.Message):
    if not await is_allowed(m.chat.id, m.from_user.id):
        return

    try:
        await bot.set_chat_permissions(
            m.chat.id,
            types.ChatPermissions(can_send_messages=True)
        )
    except:
        return await m.answer("❌ bot chưa có quyền")

    await m.answer(
        "本群已开启发言，群内可以正常作业认准群老板头衔 切勿私下交易。",
        reply_markup=build_kb()
    )

# ================= WEBHOOK =================
@app.on_event("startup")
async def startup():
    await bot.set_webhook(BASE_URL + "/webhook")

@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
        update = types.Update.model_validate(data)
        await dp.feed_update(bot, update)
    except:
        print(traceback.format_exc())

    return {"ok": True}
    
@dp.message()
async def catch_all(m: types.Message):
    print("RECEIVED:", m.text)
    await m.answer("BOT OK")
    
# ================= RUN =================
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
