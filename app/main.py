import os, asyncio, json, re, threading, requests
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from dotenv import load_dotenv
from panel import run

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

DATA="data/"

def load(f, d={}):
    try: return json.load(open(DATA+f))
    except: return d

def save(f,d):
    json.dump(d, open(DATA+f,"w"), indent=2)

def log(msg):
    try:
        requests.post(f"{BASE_URL}/log", json={"msg":msg})
    except:
        pass

# ===== WARN =====
def warn(uid):
    w = load("warns.json", {})
    uid=str(uid)
    w[uid]=w.get(uid,0)+1
    save("warns.json", w)
    return w[uid]

# ===== WALLET =====
def wallet(text):
    return re.search(r"0x[a-fA-F0-9]{40}", text)

# ===== RISK ENGINE =====
def risk(text, uid):
    cfg = load("risk.json", {})
    score = 0

    if wallet(text): score+=2
    if "http" in text: score+=1

    for w in cfg.get("risk_words", []):
        if w in text: score+=1

    return score

# ===== AUTO ADD GROUP =====
@router.my_chat_member()
async def added(e):
    g = load("groups.json", {})
    if str(e.chat.id) not in g:
        g[str(e.chat.id)] = {
            "lock":False,
            "auto_post":True,
            "post_delay":120,
            "antispam":True
        }
        save("groups.json", g)

# ===== HANDLER =====
@router.message()
async def handler(m: Message):

    if not m.text: return

    text = m.text.lower()
    uid = m.from_user.id
    gid = str(m.chat.id)

    groups = load("groups.json", {})
    if gid not in groups: return
    cfg = groups[gid]

    # ===== STATS =====
    s = load("users_stats.json", {})
    s[str(uid)] = s.get(str(uid),0)+1
    save("users_stats.json", s)

    # ===== RISK =====
    if risk(text, uid) >= 3:
        await m.delete()
        c = warn(uid)

        if c>=3:
            await bot.ban_chat_member(m.chat.id, uid)
            await m.answer("🚫 banned")
        else:
            await m.answer(f"⚠️ warn {c}/3")

        log("RISK DETECT")
        return

    # ===== LOCK =====
    if cfg.get("lock"):
        await m.delete()
        return

    # ===== TEMPLATE SAVE =====
    if text in ["ghim","pin"]:
        if m.reply_to_message:
            t = load("post_template.json", {})
            t[gid] = {"text": m.reply_to_message.text}
            save("post_template.json", t)

            await bot.pin_chat_message(m.chat.id, m.reply_to_message.message_id)
            return

# ===== AUTO POST =====
async def auto_post():
    while True:
        g = load("groups.json", {})
        t = load("post_template.json", {})

        for gid,cfg in g.items():
            if cfg.get("auto_post") and gid in t:
                try:
                    await bot.send_message(int(gid), t[gid]["text"])
                except:
                    pass

        await asyncio.sleep(60)

# ===== MAIN =====
async def main():
    await bot.delete_webhook(drop_pending_updates=True)

    asyncio.create_task(auto_post())

    threading.Thread(target=run, daemon=True).start()

    print("SYSTEM RUNNING")

    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print("RESTART:", e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
