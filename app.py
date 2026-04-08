import os
import re
import json
import time
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties

from dotenv import load_dotenv
import uvicorn

from db import (
    init_db,
    get_setting,
    set_setting,
    get_admin,
    add_admin,
    remove_admin,
    get_logs,
    log_action,
    get_all_admins,
    save_group,
    get_groups,
    add_keyword,
    get_keywords,
    get_keyword,
    remove_keyword,
    add_scheduled_post,
    get_scheduled_posts,
    get_scheduled_post,
    get_due_scheduled_posts,
    update_scheduled_post_next_run,
    update_scheduled_post,
    remove_scheduled_post
)
from ai_service import ask_ai

# ===== LOAD ENV =====
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", 8080))
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0") or 0)

# ===== BOT =====
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(link_preview_is_disabled=True)
)

dp = Dispatcher(storage=MemoryStorage())

# ===== INIT DB =====
init_db()

def init_super_admin():
    if SUPER_ADMIN_ID:
        try:
            add_admin(SUPER_ADMIN_ID, "super")
        except Exception as e:
            print("init_super_admin error:", e)

# ===== SCHEDULED POST RUNNER =====
async def scheduled_post_runner():
    while True:
        try:
            now_ts = int(time.time())
            posts = get_due_scheduled_posts(now_ts)
            for post in posts:
                post_id, chat_id, interval_min, text, image, buttons_json, enabled, next_run = post
                try:
                    markup = None
                    if buttons_json:
                        try:
                            btns_data = json.loads(buttons_json)
                            keyboard = []
                            row = []
                            for btn in btns_data:
                                row.append(InlineKeyboardButton(
                                    text=btn.get("text", ""),
                                    url=btn.get("url", "")
                                ))
                            keyboard.append(row)
                            markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
                        except Exception:
                            markup = None

                    if image:
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=image,
                            caption=text,
                            reply_markup=markup
                        )
                    else:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            reply_markup=markup
                        )
                except Exception as e:
                    print(f"scheduled_post_runner send error post_id={post_id}:", e)

                new_next_run = now_ts + int(interval_min) * 60
                update_scheduled_post_next_run(post_id, new_next_run)
        except Exception as e:
            print("scheduled_post_runner error:", e)
        await asyncio.sleep(30)

# ===== LIFESPAN =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_super_admin()
    if BASE_URL:
        try:
            webhook_url = f"{BASE_URL}/webhook"
            await bot.set_webhook(webhook_url)
            print(f"Webhook set: {webhook_url}")
        except Exception as e:
            print("set_webhook error:", e)
    asyncio.create_task(scheduled_post_runner())
    yield
    try:
        await bot.delete_webhook()
    except Exception:
        pass

# ===== FASTAPI APP =====
app = FastAPI(lifespan=lifespan)

# ===== HELPERS =====
def is_admin(user_id: int) -> bool:
    role = get_admin(user_id)
    return role in ("admin", "super")

def is_super(user_id: int) -> bool:
    return get_admin(user_id) == "super"

def build_keyboard(buttons_json: str):
    if not buttons_json:
        return None
    try:
        btns_data = json.loads(buttons_json)
        keyboard = []
        row = []
        for btn in btns_data:
            row.append(InlineKeyboardButton(
                text=btn.get("text", ""),
                url=btn.get("url", "")
            ))
        keyboard.append(row)
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    except Exception:
        return None

# ===== TELEGRAM WEBHOOK =====
@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print("webhook error:", e)
    return {"ok": True}

# ===== HEALTH CHECK =====
@app.get("/")
async def health():
    return {"status": "ok", "service": "thriving-passion"}

# ===== AIOGRAM HANDLERS =====

# --- New member welcome ---
@dp.chat_member()
async def on_chat_member(event: types.ChatMemberUpdated):
    if event.new_chat_member.status not in ("member", "restricted"):
        return
    user = event.new_chat_member.user
    chat = event.chat

    save_group(chat.id, chat.title or str(chat.id))

    welcome_text = get_setting("welcome_text") or "Welcome {name} to {group}!"
    buttons_json = get_setting("welcome_buttons")

    text = welcome_text.replace("{name}", user.full_name).replace("{group}", chat.title or "")

    markup = build_keyboard(buttons_json)

    try:
        await bot.send_message(
            chat_id=chat.id,
            text=text,
            reply_markup=markup
        )
    except Exception as e:
        print("welcome send error:", e)

# --- Message handler ---
@dp.message()
async def on_message(message: types.Message):
    if not message.text:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()

    # Save group
    if message.chat.type in ("group", "supergroup"):
        save_group(chat_id, message.chat.title or str(chat_id))

    # Admin commands
    if text.startswith("/"):
        await handle_command(message, user_id, chat_id, text)
        return

    # Keyword auto-reply
    text_lower = text.lower()
    keywords = get_keywords()
    for kw in keywords:
        key, reply, image, buttons_json = kw
        if key.lower() in text_lower:
            markup = build_keyboard(buttons_json)
            try:
                if image:
                    await message.answer_photo(photo=image, caption=reply, reply_markup=markup)
                else:
                    await message.answer(reply, reply_markup=markup)
            except Exception as e:
                print("keyword reply error:", e)
            log_action(user_id, f"keyword:{key}", chat_id)
            return

    # AI fallback (only in private chat)
    if message.chat.type == "private":
        try:
            reply = await ask_ai(user_id, text)
            if reply:
                await message.answer(reply)
        except Exception as e:
            print("ai reply error:", e)

async def handle_command(message: types.Message, user_id: int, chat_id: int, text: str):
    parts = text.split()
    cmd = parts[0].lower().split("@")[0]

    # /start
    if cmd == "/start":
        await message.answer("👋 Bot is running. Use /help for commands.")
        return

    # /help
    if cmd == "/help":
        help_text = (
            "📋 *Commands:*\n"
            "/start — Start the bot\n"
            "/help — Show this help\n"
            "/admins — List admins\n"
            "/addkw <key> | <reply> — Add keyword reply\n"
            "/delkw <key> — Delete keyword reply\n"
            "/listkw — List all keywords\n"
            "/setwelcome <text> — Set welcome message\n"
            "/groups — List saved groups\n"
            "/logs — Show recent logs\n"
            "/addadmin <user_id> — Add admin (super only)\n"
            "/deladmin <user_id> — Remove admin (super only)\n"
            "/broadcast <text> — Broadcast to all groups\n"
            "/schedpost <chat_id> <interval_min> <text> — Schedule a post\n"
            "/listposts — List scheduled posts\n"
            "/delpost <id> — Delete scheduled post\n"
        )
        await message.answer(help_text, parse_mode="Markdown")
        return

    # /admins
    if cmd == "/admins":
        admins = get_all_admins()
        if not admins:
            await message.answer("No admins found.")
            return
        lines = [f"• `{a[0]}` — {a[1]}" for a in admins]
        await message.answer("👮 *Admins:*\n" + "\n".join(lines), parse_mode="Markdown")
        return

    # /addadmin (super only)
    if cmd == "/addadmin":
        if not is_super(user_id):
            await message.answer("⛔ Super admin only.")
            return
        if len(parts) < 2:
            await message.answer("Usage: /addadmin <user_id>")
            return
        try:
            target_id = int(parts[1])
            add_admin(target_id, "admin")
            log_action(user_id, f"addadmin:{target_id}", chat_id)
            await message.answer(f"✅ Admin added: `{target_id}`", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"Error: {e}")
        return

    # /deladmin (super only)
    if cmd == "/deladmin":
        if not is_super(user_id):
            await message.answer("⛔ Super admin only.")
            return
        if len(parts) < 2:
            await message.answer("Usage: /deladmin <user_id>")
            return
        try:
            target_id = int(parts[1])
            remove_admin(target_id)
            log_action(user_id, f"deladmin:{target_id}", chat_id)
            await message.answer(f"✅ Admin removed: `{target_id}`", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"Error: {e}")
        return

    # /addkw (admin only)
    if cmd == "/addkw":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        raw = text[len("/addkw"):].strip()
        if "|" not in raw:
            await message.answer("Usage: /addkw <key> | <reply>")
            return
        key_part, reply_part = raw.split("|", 1)
        key_part = key_part.strip()
        reply_part = reply_part.strip()
        if not key_part or not reply_part:
            await message.answer("Usage: /addkw <key> | <reply>")
            return
        add_keyword(key_part, reply_part)
        log_action(user_id, f"addkw:{key_part}", chat_id)
        await message.answer(f"✅ Keyword added: `{key_part}`", parse_mode="Markdown")
        return

    # /delkw (admin only)
    if cmd == "/delkw":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        if len(parts) < 2:
            await message.answer("Usage: /delkw <key>")
            return
        key_part = " ".join(parts[1:]).strip()
        remove_keyword(key_part)
        log_action(user_id, f"delkw:{key_part}", chat_id)
        await message.answer(f"✅ Keyword removed: `{key_part}`", parse_mode="Markdown")
        return

    # /listkw
    if cmd == "/listkw":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        keywords = get_keywords()
        if not keywords:
            await message.answer("No keywords set.")
            return
        lines = [f"• `{kw[0]}` → {kw[1]}" for kw in keywords]
        await message.answer("🔑 *Keywords:*\n" + "\n".join(lines), parse_mode="Markdown")
        return

    # /setwelcome (admin only)
    if cmd == "/setwelcome":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        welcome = text[len("/setwelcome"):].strip()
        if not welcome:
            await message.answer("Usage: /setwelcome <text>\nUse {name} and {group} as placeholders.")
            return
        set_setting("welcome_text", welcome)
        log_action(user_id, "setwelcome", chat_id)
        await message.answer("✅ Welcome message updated.")
        return

    # /groups
    if cmd == "/groups":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        groups = get_groups()
        if not groups:
            await message.answer("No groups saved.")
            return
        lines = [f"• `{g[0]}` — {g[1]}" for g in groups]
        await message.answer("👥 *Groups:*\n" + "\n".join(lines), parse_mode="Markdown")
        return

    # /logs
    if cmd == "/logs":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        logs = get_logs()
        if not logs:
            await message.answer("No logs found.")
            return
        recent = logs[:20]
        lines = [f"• [{l[0]}] user={l[1]} action={l[2]} chat={l[3]}" for l in recent]
        await message.answer("📋 *Recent Logs:*\n" + "\n".join(lines), parse_mode="Markdown")
        return

    # /broadcast (admin only)
    if cmd == "/broadcast":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        bcast_text = text[len("/broadcast"):].strip()
        if not bcast_text:
            await message.answer("Usage: /broadcast <text>")
            return
        groups = get_groups()
        sent = 0
        failed = 0
        for g in groups:
            try:
                await bot.send_message(chat_id=g[0], text=bcast_text)
                sent += 1
            except Exception:
                failed += 1
        log_action(user_id, "broadcast", chat_id)
        await message.answer(f"📢 Broadcast done. Sent: {sent}, Failed: {failed}")
        return

    # /schedpost (admin only)
    if cmd == "/schedpost":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        # Usage: /schedpost <chat_id> <interval_min> <text>
        if len(parts) < 4:
            await message.answer("Usage: /schedpost <chat_id> <interval_min> <text>")
            return
        try:
            target_chat = int(parts[1])
            interval = int(parts[2])
            post_text = " ".join(parts[3:])
            add_scheduled_post(target_chat, interval, post_text)
            log_action(user_id, f"schedpost:{target_chat}", chat_id)
            await message.answer(f"✅ Scheduled post added for chat `{target_chat}` every {interval} min.", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"Error: {e}")
        return

    # /listposts (admin only)
    if cmd == "/listposts":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        posts = get_scheduled_posts()
        if not posts:
            await message.answer("No scheduled posts.")
            return
        lines = [f"• ID={p[0]} chat={p[1]} every={p[2]}min: {p[3][:40]}" for p in posts]
        await message.answer("📅 *Scheduled Posts:*\n" + "\n".join(lines), parse_mode="Markdown")
        return

    # /delpost (admin only)
    if cmd == "/delpost":
        if not is_admin(user_id):
            await message.answer("⛔ Admins only.")
            return
        if len(parts) < 2:
            await message.answer("Usage: /delpost <id>")
            return
        try:
            post_id = int(parts[1])
            remove_scheduled_post(post_id)
            log_action(user_id, f"delpost:{post_id}", chat_id)
            await message.answer(f"✅ Scheduled post {post_id} removed.")
        except Exception as e:
            await message.answer(f"Error: {e}")
        return

# ===== HTTP API ROUTES =====

# --- Admin management ---
@app.get("/api/admins")
async def api_get_admins():
    admins = get_all_admins()
    return {"admins": [{"user_id": a[0], "role": a[1]} for a in admins]}

@app.post("/api/admins/add")
async def api_add_admin(data: dict):
    user_id = data.get("user_id")
    role = data.get("role", "admin")
    if not user_id:
        return JSONResponse({"error": "user_id required"}, status_code=400)
    add_admin(int(user_id), role)
    return {"ok": True}

@app.post("/api/admins/remove")
async def api_remove_admin(data: dict):
    user_id = data.get("user_id")
    if not user_id:
        return JSONResponse({"error": "user_id required"}, status_code=400)
    remove_admin(int(user_id))
    return {"ok": True}

# --- Groups ---
@app.get("/api/groups")
async def api_get_groups():
    groups = get_groups()
    return {"groups": [{"chat_id": g[0], "name": g[1]} for g in groups]}

@app.post("/api/groups/save")
async def api_save_group(data: dict):
    chat_id = data.get("chat_id")
    name = data.get("name", "")
    if not chat_id:
        return JSONResponse({"error": "chat_id required"}, status_code=400)
    save_group(int(chat_id), name)
    return {"ok": True}

# --- Keywords ---
@app.get("/api/keywords")
async def api_get_keywords():
    keywords = get_keywords()
    return {"keywords": [{"key": k[0], "reply": k[1], "image": k[2], "buttons": k[3]} for k in keywords]}

@app.get("/api/keywords/{key}")
async def api_get_keyword(key: str):
    kw = get_keyword(key)
    if not kw:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"key": kw[0], "reply": kw[1], "image": kw[2], "buttons": kw[3]}

@app.post("/api/keywords/add")
async def api_add_keyword(data: dict):
    key = data.get("key")
    reply = data.get("reply")
    image = data.get("image")
    buttons = data.get("buttons")
    if not key or not reply:
        return JSONResponse({"error": "key and reply required"}, status_code=400)
    add_keyword(key, reply, image, buttons)
    return {"ok": True}

@app.post("/api/keywords/remove")
async def api_remove_keyword(data: dict):
    key = data.get("key")
    if not key:
        return JSONResponse({"error": "key required"}, status_code=400)
    remove_keyword(key)
    return {"ok": True}

# --- Settings ---
@app.get("/api/settings/{key}")
async def api_get_setting(key: str):
    value = get_setting(key)
    return {"key": key, "value": value}

@app.post("/api/settings")
async def api_set_setting(data: dict):
    key = data.get("key")
    value = data.get("value")
    if not key:
        return JSONResponse({"error": "key required"}, status_code=400)
    set_setting(key, value)
    return {"ok": True}

# --- Logs ---
@app.get("/api/logs")
async def api_get_logs():
    logs = get_logs()
    return {"logs": [{"id": l[0], "user_id": l[1], "action": l[2], "chat_id": l[3], "time": str(l[4])} for l in logs]}

# --- Scheduled posts ---
@app.get("/api/posts")
async def api_get_posts():
    posts = get_scheduled_posts()
    return {"posts": [
        {"id": p[0], "chat_id": p[1], "interval_min": p[2], "text": p[3],
         "image": p[4], "buttons": p[5], "enabled": p[6], "next_run": p[7]}
        for p in posts
    ]}

@app.get("/api/posts/{post_id}")
async def api_get_post(post_id: int):
    post = get_scheduled_post(post_id)
    if not post:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"id": post[0], "chat_id": post[1], "interval_min": post[2], "text": post[3],
            "image": post[4], "buttons": post[5], "enabled": post[6], "next_run": post[7]}

@app.post("/api/posts/add")
async def api_add_post(data: dict):
    chat_id = data.get("chat_id")
    interval_min = data.get("interval_min")
    text = data.get("text")
    image = data.get("image")
    buttons = data.get("buttons")
    if not chat_id or not interval_min or not text:
        return JSONResponse({"error": "chat_id, interval_min, and text required"}, status_code=400)
    add_scheduled_post(int(chat_id), int(interval_min), text, image, buttons)
    return {"ok": True}

@app.post("/api/posts/update")
async def api_update_post(data: dict):
    post_id = data.get("id")
    if not post_id:
        return JSONResponse({"error": "id required"}, status_code=400)
    ok = update_scheduled_post(
        int(post_id),
        interval_min=data.get("interval_min"),
        text=data.get("text"),
        image=data.get("image"),
        buttons=data.get("buttons"),
        enabled=data.get("enabled")
    )
    if not ok:
        return JSONResponse({"error": "post not found"}, status_code=404)
    return {"ok": True}

@app.post("/api/posts/remove")
async def api_remove_post(data: dict):
    post_id = data.get("id")
    if not post_id:
        return JSONResponse({"error": "id required"}, status_code=400)
    remove_scheduled_post(int(post_id))
    return {"ok": True}

# --- Broadcast ---
@app.post("/api/broadcast")
async def api_broadcast(data: dict):
    text = data.get("text")
    image = data.get("image")
    buttons_json = data.get("buttons")
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)

    groups = get_groups()
    markup = build_keyboard(buttons_json)
    sent = 0
    failed = 0

    for g in groups:
        try:
            if image:
                await bot.send_photo(chat_id=g[0], photo=image, caption=text, reply_markup=markup)
            else:
                await bot.send_message(chat_id=g[0], text=text, reply_markup=markup)
            sent += 1
        except Exception:
            failed += 1

    return {"ok": True, "sent": sent, "failed": failed}

# --- AI ---
@app.post("/api/ai")
async def api_ai(data: dict):
    user_id = data.get("user_id", 0)
    text = data.get("text")
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    reply = await ask_ai(int(user_id), text)
    return {"reply": reply}

# --- Welcome settings ---
@app.get("/api/welcome")
async def api_get_welcome():
    text = get_setting("welcome_text")
    buttons = get_setting("welcome_buttons")
    return {"text": text, "buttons": buttons}

@app.post("/api/welcome")
async def api_set_welcome(data: dict):
    text = data.get("text")
    buttons = data.get("buttons")
    if text is not None:
        set_setting("welcome_text", text)
    if buttons is not None:
        set_setting("welcome_buttons", buttons)
    return {"ok": True}

# ===== ENTRY POINT =====
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
