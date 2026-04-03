import os, asyncio, json, re, time, threading, logging, requests
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import Message
from dotenv import load_dotenv
from panel import run

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
ADMIN = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

DATA = "data/"
USER_MSG = {}

logging.basicConfig(level=logging.INFO)

# ===== UTILS =====
def load(f, d={}):
    try: return json.load(open(DATA+f))
    except: return d

def save(f, d):
    json.dump(d, open(DATA+f,"w"), indent=2)

def log(msg):
    try:
        requests.post(f"{BASE_URL}/log", json={"msg":msg})
    except:
        pass

# ===== SPAM =====
def spam_check(uid):
    now = time.time()
    arr = USER_MSG.get(uid, [])
    arr = [t for t in arr if now - t < 5]
    arr.append(now)
    USER_MSG[uid] = arr
    return len(arr) > 5

# ===== WARN =====
def warn(uid):
    w = load("warns.json", {})
    uid=str(uid)
    w[uid]=w.get(uid,0)+1
    save("warns.json", w)
    return w[uid]

# ===== ROLE =====
def is_admin(uid):
    roles = load("roles.json", {})
    return uid in roles.get("owner", []) or uid in roles.get("admin", [])

# ===== KEYWORD =====
def load_keywords():
    return load("keywords.json", {})

# ===== AUTO ADD GROUP =====
@router.my_chat_member()
async def added(e):
    g = load("groups.json", {})
    if str(e.chat.id) not in g:
        g[str(e.chat.id)] = {
            "lock": False,
            "auto_post": True,
            "post_delay": 120,
            "antispam": True
        }
        save("groups.json", g)

# ===== HANDLER =====
@router.message()
async def handler(m: Message):

    if not m.text:
        return

    text = m.text.lower()
    uid = m.from_user.id
    gid = str(m.chat.id)

    groups = load("groups.json", {})
    if gid not in groups:
        return

    cfg = groups[gid]

    # ===== SPAM =====
    if spam_check(uid):
        await m.delete()
        return

    # ===== AI SIMPLE FILTER =====
    bad = ["airdrop", "free", "赚", "赚钱"]
    if any(w in text for w in bad):
        await m.delete()
        await bot.ban_chat_member(m.chat.id, uid)
        return

    # ===== KEYWORD =====
    keywords = load_keywords()

    if gid in keywords:
        for item in keywords[gid]:
            if item["key"] in text:

                if item.get("text"):
                    await m.answer(item["text"])

                for f in item.get("files", []):
                    path = f"static/{f}"
                    try:
                        if f.endswith(".jpg") or f.endswith(".png"):
                            await bot.send_photo(m.chat.id, photo=open(path,"rb"))
                        elif f.endswith(".mp4"):
                            await bot.send_video(m.chat.id, video=open(path,"rb"))
                    except:
                        pass

                if item.get("buttons"):
                    kb = types.InlineKeyboardMarkup(
                        inline_keyboard=[
                            [types.InlineKeyboardButton(text=b["text"], url=b["url"])]
                            for b in item["buttons"]
                        ]
                    )
                    await m.answer("🔗 Link:", reply_markup=kb)

                return

    # ===== LOCK =====
    if cfg.get("lock"):
        await m.delete()
        return

    # ===== ADMIN =====
    if is_admin(uid):

        if text == "/stats":
            s = load("users_stats.json", {})
            await m.answer(str(s))

        if text.startswith("/addkey"):
            try:
                _, key, msg = text.split(" ",2)
                kw = load("keywords.json", {})
                kw.setdefault(gid, []).append({
                    "key": key,
                    "text": msg
                })
                save("keywords.json", kw)
                await m.answer("✅ added")
            except:
                await m.answer("❌ error")

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

# ===== HEALTH =====
async def health(request):
    return web.Response(text="OK")

# ===== WEBHOOK =====
async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="OK")

# ===== MAIN =====
async def main():
    await bot.delete_webhook(drop_pending_updates=True)

    asyncio.create_task(auto_post())
    threading.Thread(target=run, daemon=True).start()

    print("🚀 SYSTEM RUNNING")

    app = web.Application()

    app.router.add_post(f"/{BOT_TOKEN}", handle)
    app.router.add_get("/", health)

    async def on_startup(app):
        await bot.set_webhook(f"{BASE_URL}/{BOT_TOKEN}")
        logging.info("✅ Webhook set")

    async def on_shutdown(app):
        await bot.session.close()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)

    await site.start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
