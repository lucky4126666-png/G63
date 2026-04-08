import os
import re
import time
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

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

# ================= HELPER =================
def is_cmd(message: types.Message, *cmds):
    if not message.text:
        return False

    txt = message.text.strip().split()[0].lower()
    txt = txt.split("@")[0]  # bỏ @botname nếu có
    return txt in [c.lower() for c in cmds]

async def is_allowed(chat_id, user_id):
    role = get_admin(user_id)
    if role in ("super", "admin"):
        return True

    admins = await bot.get_chat_administrators(chat_id)
    return any(a.user.id == user_id for a in admins)

def normalize_key(key: str):
    if not key:
        return ""
    return re.sub(r"\s+", "", key).strip()

def extract_target_user_id(message: types.Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    parts = (message.text or "").split()
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])

    return None

def parse_block_fields(body: str):
    """
    Parse dạng:
    key: hello
    reply: Xin chào
    image: https://...
    buttons: Nút 1|https://a.com;Nút 2|https://b.com
    interval: 30
    text: Nội dung
    """
    data = {}
    current_field = None

    for raw_line in (body or "").splitlines():
        line = raw_line.rstrip()

        if not line.strip():
            if current_field:
                data[current_field] = data.get(current_field, "") + "\n"
            continue

        m = re.match(r"^([A-Za-z_]+)\s*:\s*(.*)$", line)
        if m:
            current_field = m.group(1).strip().lower()
            data[current_field] = m.group(2).rstrip()
        else:
            if current_field:
                data[current_field] = (data.get(current_field, "") + "\n" + line).rstrip("\n")

    return data

def get_message_content(msg: types.Message):
    if not msg:
        return ""
    return (msg.text or msg.caption or "").strip()

def get_replied_image_file_id(msg: types.Message):
    if not msg:
        return None

    if msg.photo:
        return msg.photo[-1].file_id

    if msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
        return msg.document.file_id

    return None

def build_buttons(buttons_text):
    """
    buttons: Nút 1|https://a.com;Nút 2|https://b.com;Nút 3|https://c.com;Nút 4|https://d.com
    Tự chia 2 nút / hàng => 4 nút sẽ ra 2x2
    """
    if not buttons_text:
        return None

    items = re.split(r"[;\n]+", buttons_text.strip())
    buttons = []

    for item in items:
        item = item.strip()
        if not item or "|" not in item:
            continue

        label, url = item.split("|", 1)
        label = label.strip()
        url = url.strip()

        if label and url:
            buttons.append(InlineKeyboardButton(text=label, url=url))

    if not buttons:
        return None

    rows = []
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i + 2])

    return InlineKeyboardMarkup(inline_keyboard=rows)

def find_keyword_match(text):
    if not text:
        return None

    keys = get_keywords()
    if not keys:
        return None

    keys = sorted(keys, key=lambda x: len(x[0]), reverse=True)
    lower_text = normalize_key(text).lower()

    for key, reply, image, buttons in keys:
        if normalize_key(key).lower() in lower_text:
            return {
                "key": key,
                "reply": reply,
                "image": image,
                "buttons": buttons
            }

    return None

async def send_text_or_photo(chat_id, text, image=None, buttons=None):
    kb = build_buttons(buttons)

    if image:
        try:
            if len(text) <= 1024:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image,
                    caption=text,
                    reply_markup=kb
                )
            else:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=image,
                    reply_markup=kb
                )
                await bot.send_message(chat_id, text)
        except Exception as e:
            print("send_photo failed:", e)
            await bot.send_message(chat_id, text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

async def send_keyword_reply(message: types.Message, match: dict):
    try:
        kb = build_buttons(match["buttons"])

        if match["image"]:
            try:
                if len(match["reply"]) <= 1024:
                    await message.answer_photo(
                        photo=match["image"],
                        caption=match["reply"],
                        reply_markup=kb
                    )
                else:
                    await message.answer_photo(
                        photo=match["image"],
                        reply_markup=kb
                    )
                    await message.reply(match["reply"])
            except Exception as e:
                print("keyword send_photo failed:", e)
                await message.reply(match["reply"], reply_markup=kb)
        else:
            await message.reply(match["reply"], reply_markup=kb)
    except Exception as e:
        print("send_keyword_reply error:", e)

async def auto_post_loop():
    while True:
        try:
            now_ts = int(time.time())
            due_posts = get_due_scheduled_posts(now_ts)

            for post in due_posts:
                post_id, chat_id, interval_min, text, image, buttons, enabled, next_run = post

                try:
                    await send_text_or_photo(chat_id, text, image, buttons)
                except Exception as e:
                    print(f"auto_post post_id={post_id} error:", e)
                finally:
                    try:
                        new_next_run = now_ts + int(interval_min) * 60
                        update_scheduled_post_next_run(post_id, new_next_run)
                    except Exception as e:
                        print(f"auto_post update next_run error post_id={post_id}:", e)

        except Exception as e:
            print("auto_post_loop error:", e)

        await asyncio.sleep(30)

# ================= LIFESPAN =================
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_super_admin()

    webhook_url = (BASE_URL or "").rstrip("/") + "/webhook"
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(webhook_url)
    except Exception as e:
        print("webhook setup error:", e)

    task = asyncio.create_task(auto_post_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except:
            pass

app = FastAPI(lifespan=lifespan)

# ================= ADMIN COMMANDS =================
@dp.message(lambda m: m.text and is_cmd(m, "/addadmin", "/promote"))
async def add_admin_cmd(m: types.Message):
    if get_admin(m.from_user.id) != "super":
        return await m.reply("❌ Chỉ super admin mới có quyền cấp admin")

    user_id = extract_target_user_id(m)
    if not user_id:
        return await m.reply(
            "Cách dùng:\n"
            "/addadmin 123456789\n"
            "Hoặc reply vào tin nhắn của người đó rồi gõ /addadmin"
        )

    add_admin(user_id, "admin")
    log_action(m.from_user.id, "add_admin", m.chat.id)
    await m.reply(f"✅ Đã cấp quyền admin cho user_id: {user_id}")

@dp.message(lambda m: m.text and is_cmd(m, "/deladmin", "/demote"))
async def del_admin_cmd(m: types.Message):
    if get_admin(m.from_user.id) != "super":
        return await m.reply("❌ Chỉ super admin mới có quyền gỡ admin")

    user_id = extract_target_user_id(m)
    if not user_id:
        return await m.reply(
            "Cách dùng:\n"
            "/deladmin 123456789\n"
            "Hoặc reply vào tin nhắn của người đó rồi gõ /deladmin"
        )

    remove_admin(user_id)
    log_action(m.from_user.id, "del_admin", m.chat.id)
    await m.reply(f"✅ Đã gỡ quyền admin cho user_id: {user_id}")

@dp.message(lambda m: m.text and is_cmd(m, "/admins"))
async def list_admins_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ Không có quyền")

    admins = get_all_admins()
    if not admins:
        return await m.reply("Chưa có admin nào")

    text = "📋 Danh sách admin:\n\n"
    for user_id, role in admins:
        text += f"• `{user_id}` — {role}\n"

    await m.reply(text, parse_mode="Markdown")

@dp.message(lambda m: m.text and is_cmd(m, "/myrole"))
async def myrole_cmd(m: types.Message):
    role = get_admin(m.from_user.id)
    if role:
        await m.reply(f"👤 Quyền của bạn: {role}")
    else:
        await m.reply("👤 Bạn hiện chưa có quyền trong hệ thống")

# ================= KEY COMMANDS =================
@dp.message(lambda m: m.text and is_cmd(m, "/addkey"))
async def add_key_cmd(m: types.Message):
    try:
        if get_admin(m.from_user.id) not in ("super", "admin"):
            return await m.reply("❌ 无权限")

        body = m.text[len("/addkey"):].strip()

        key = None
        reply_text = None
        image = None
        buttons = None

        if m.reply_to_message:
            image = get_replied_image_file_id(m.reply_to_message)

        replied_content = get_message_content(m.reply_to_message) if m.reply_to_message else ""

        if "\n" in body or "key:" in body.lower():
            data = parse_block_fields(body)
            key = data.get("key") or data.get("keyword")
            reply_text = data.get("reply")
            image = data.get("image") or image
            buttons = data.get("buttons")
        else:
            parts = body.split("|", 3)
            if len(parts) >= 1:
                key = parts[0].strip() or None
            if len(parts) >= 2:
                reply_text = parts[1].strip() or None
            if len(parts) >= 3:
                image = parts[2].strip() or image
            if len(parts) >= 4:
                buttons = parts[3].strip() or None

        if not reply_text and replied_content:
            reply_text = replied_content

        if not key or not reply_text:
            return await m.reply(
                "❌ Thiếu key hoặc nội dung bài viết\n\n"
                "Cách dùng:\n"
                "1) Reply vào bài viết rồi gõ:\n"
                "/addkey 上押\n\n"
                "2) Hoặc:\n"
                "/addkey 上押|Nội dung trả lời\n\n"
                "3) Hoặc dạng block:\n"
                "/addkey\n"
                "key: 上押\n"
                "reply: Nội dung trả lời\n"
                "image: file_id_ảnh hoặc link ảnh\n"
                "buttons: Nút 1|url;Nút 2|url;Nút 3|url;Nút 4|url"
            )

        key = normalize_key(key)
        add_keyword(key, reply_text, image, buttons)
        log_action(m.from_user.id, "add_keyword", m.chat.id)
        await m.reply(f"✅ Đã lưu key: {key}")

    except Exception as e:
        print("add_key_cmd error:", e)
        await m.reply(f"❌ Lỗi khi lưu key: {e}")

@dp.message(lambda m: m.text and is_cmd(m, "/editkey"))
async def edit_key_cmd(m: types.Message):
    try:
        if get_admin(m.from_user.id) not in ("super", "admin"):
            return await m.reply("❌ 无权限")

        body = m.text[len("/editkey"):].strip()

        key = None
        reply_text = None
        image = None
        buttons = None

        if m.reply_to_message:
            image = get_replied_image_file_id(m.reply_to_message)

        replied_content = get_message_content(m.reply_to_message) if m.reply_to_message else ""

        if "\n" in body or "key:" in body.lower():
            data = parse_block_fields(body)
            key = data.get("key") or data.get("keyword")
            reply_text = data.get("reply")
            image = data.get("image") or image
            buttons = data.get("buttons")
        else:
            parts = body.split("|", 3)
            if len(parts) >= 1:
                key = parts[0].strip() or None
            if len(parts) >= 2:
                reply_text = parts[1].strip() or None
            if len(parts) >= 3:
                image = parts[2].strip() or image
            if len(parts) >= 4:
                buttons = parts[3].strip() or None

        if not reply_text and replied_content:
            reply_text = replied_content

        if not key:
            return await m.reply("❌ Thiếu key")

        key = normalize_key(key)
        old = get_keyword(key)
        if not old:
            return await m.reply("❌ Không tìm thấy key này")

        _, old_reply, old_image, old_buttons = old

        new_reply = reply_text if reply_text is not None else old_reply
        new_image = image if image is not None else old_image
        new_buttons = buttons if buttons is not None else old_buttons

        add_keyword(key, new_reply, new_image, new_buttons)
        log_action(m.from_user.id, "edit_keyword", m.chat.id)
        await m.reply(f"✅ Đã cập nhật key: {key}")

    except Exception as e:
        print("edit_key_cmd error:", e)
        await m.reply(f"❌ Lỗi khi sửa key: {e}")

@dp.message(lambda m: m.text and is_cmd(m, "/showkey"))
async def show_key_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.reply("Cách dùng: /showkey hello")

    key = normalize_key(parts[1].strip())
    row = get_keyword(key)

    if not row:
        return await m.reply("❌ Không tìm thấy key")

    k, reply, image, buttons = row
    text = (
        f"📌 Key: {k}\n\n"
        f"📝 Reply:\n{reply}\n\n"
        f"🖼 Image: {image or 'None'}\n"
        f"🔘 Buttons: {buttons or 'None'}"
    )
    await m.reply(text)

@dp.message(lambda m: m.text and is_cmd(m, "/delkey"))
async def del_key_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.reply("Cách dùng: /delkey hello")

    key = normalize_key(parts[1].strip())
    if not key:
        return await m.reply("❌ Key trống")

    remove_keyword(key)
    log_action(m.from_user.id, "del_keyword", m.chat.id)
    await m.reply(f"✅ Đã xoá key: {key}")

@dp.message(lambda m: m.text and is_cmd(m, "/keys"))
async def list_keys_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    keys = get_keywords()
    if not keys:
        return await m.reply("Chưa có key nào")

    text = "📋 Danh sách key:\n\n"
    for key, reply, image, buttons in keys:
        flag = []
        if image:
            flag.append("🖼")
        if buttons:
            flag.append("🔘")
        flag_text = " ".join(flag) if flag else ""
        text += f"• `{key}` {flag_text}\n"

    await m.reply(text, parse_mode="Markdown")

# ================= HELP / GROUP / DELETE =================
@dp.message(lambda m: m.text and is_cmd(m, "/help"))
async def help_cmd(m: types.Message):
    if m.chat.type != "private":
        return

    text = (
        "📖 <b>HƯỚNG DẪN SỬ DỤNG BOT</b>\n\n"

        "👤 <b>QUYỀN HẠN</b>\n"
        "• /myrole — xem quyền của bạn\n"
        "• /admins — xem danh sách admin\n"
        "• /promote — cấp admin (chỉ super admin)\n"
        "• /demote — gỡ admin (chỉ super admin)\n\n"

        "🏠 <b>GROUP</b>\n"
        "• /groupid hoặc /id — xem ID group\n"
        "• /lock hoặc 下课 — khóa nhóm\n"
        "• /open hoặc 上课 — mở nhóm\n"
        "• ghimmes — ghim bài (reply vào bài)\n"
        "• /delmsg — xoá bài (reply vào bài)\n\n"

        "🔑 <b>KEY</b>\n"
        "• /addkey key|reply|image|buttons\n"
        "• /editkey key|reply|image|buttons\n"
        "• /showkey key\n"
        "• /delkey key\n"
        "• /keys\n\n"

        "🕒 <b>AUTO POST</b>\n"
        "• /addpost\n"
        "  interval: 30\n"
        "  text: nội dung\n"
        "  image: link ảnh hoặc file_id\n"
        "  buttons: Nút 1|url;Nút 2|url;Nút 3|url;Nút 4|url\n"
        "• /editpost 1\n"
        "• /showpost 1\n"
        "• /delpost 1\n"
        "• /posts\n\n"

        "🤖 <b>LƯU Ý</b>\n"
        "• Trong group bot chỉ phản hồi key đã lưu\n"
        "• Reply vào ảnh để bot tự lấy file_id ảnh\n"
        "• Ảnh nên là link trực tiếp hoặc file_id Telegram\n"
        "• Lệnh trong group giữ nguyên như cũ\n"
    )

    await m.reply(text, parse_mode="HTML")

@dp.message(lambda m: m.text and is_cmd(m, "/groupid", "/id"))
async def group_id_cmd(m: types.Message):
    if m.chat.type == "private":
        return await m.reply("Lệnh này dùng trong group để xem ID group.")

    await m.reply(f"📌 ID của group này là:\n`{m.chat.id}`", parse_mode="Markdown")

@dp.message(lambda m: m.text and is_cmd(m, "/delmsg", "/delete", "/xoa"))
async def delete_message_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    if not m.reply_to_message:
        return await m.reply("❌ Hãy reply vào bài viết cần xoá rồi gõ /delmsg")

    try:
        await bot.delete_message(
            chat_id=m.chat.id,
            message_id=m.reply_to_message.message_id
        )
        await m.reply("✅ Đã xoá bài viết")
    except Exception as e:
        await m.reply("❌ Bot không có quyền xoá tin nhắn")
        print("delete_message_cmd error:", e)

# ================= START =================
@dp.message(lambda m: m.text and is_cmd(m, "/start"))
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
    try:
        if e.old_chat_member.status == "left" and e.new_chat_member.status in ("member", "administrator"):
            chat_id = e.chat.id
            save_group(chat_id, e.chat.title)

            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="公群导航", url="https://t.me/xbkf"),
                InlineKeyboardButton(text="供需频道", url="https://t.me/xbkf")
            ]])

            try:
                await bot.send_message(
                    chat_id,
                    "组防骗助手为您服务,我正在进行相关初始化配置请稍后",
                    reply_markup=kb
                )
            except Exception as e:
                print("bot_join welcome send failed:", e)

            admins = await bot.get_chat_administrators(chat_id)
            admin_ids = [a.user.id for a in admins]

            has_admin = any(get_admin(uid) for uid in admin_ids)
            has_super_admin = any(get_admin(uid) == "super" for uid in admin_ids)

            if not has_admin and not has_super_admin:
                try:
                    await bot.send_message(
                        chat_id,
                        "⚠️ 风险提示，本群没有检测到新币管理员。\n"
                        "有交易风险，请联系新币工作人员确认 @xbkf"
                    )
                except Exception as e:
                    print("bot_join risk send failed:", e)

    except Exception as e:
        print("bot_join error:", e)

# ================= USER JOIN =================
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

        try:
            await m.answer(text, reply_markup=kb)
        except Exception as e:
            print("welcome send failed:", e)

# ================= LOCK =================
@dp.message(lambda m: m.text and is_cmd(m, "/lock", "下课"))
async def lock_group(m: types.Message):
    if not await is_allowed(m.chat.id, m.from_user.id):
        return await m.reply("❌ 无权限")

    try:
        await bot.set_chat_permissions(
            m.chat.id,
            permissions=types.ChatPermissions(can_send_messages=False)
        )
    except Exception as e:
        await m.reply("❌ 机器人没有权限修改群发言权限")
        print("lock_group error:", e)
        return

    log_action(m.from_user.id, "lock", m.chat.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="新币供需", url="https://t.me/xbkf"),
        InlineKeyboardButton(text="新币公群", url="https://t.me/xbkf")
    ]])

    try:
        await m.answer(
            "本公群已下课关闭发言\n如需交易，请恢复后操作！",
            reply_markup=kb
        )
    except Exception as e:
        print("lock_group send failed:", e)

# ================= OPEN =================
@dp.message(lambda m: m.text and is_cmd(m, "/open", "上课"))
async def open_group(m: types.Message):
    if not await is_allowed(m.chat.id, m.from_user.id):
        return await m.reply("❌ 无权限")

    try:
        await bot.set_chat_permissions(
            m.chat.id,
            permissions=types.ChatPermissions(can_send_messages=True)
        )
    except Exception as e:
        await m.reply("❌ 机器人没有权限修改群发言权限")
        print("open_group error:", e)
        return

    log_action(m.from_user.id, "open", m.chat.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="新币供需", url="https://t.me/xbkf"),
        InlineKeyboardButton(text="新币公群", url="https://t.me/xbkf")
    ]])

    try:
        await m.answer(
            "本群已开启发言，可以正常作业",
            reply_markup=kb
        )
    except Exception as e:
        print("open_group send failed:", e)

# ================= RENAME GROUP (担保表单) =================
@dp.message(lambda m: m.text and "担保表单" in m.text)
async def rename_group(m: types.Message):
    role = get_admin(m.from_user.id)
    if role not in ("admin", "super"):
        return await m.reply("❌ 无权限")

    text = m.text.replace("\n", " ")

    def find(pattern):
        r = re.search(pattern, text)
        return r.group(1).strip() if r else ""

    group = find(r"组别[:：]\s*([^\s]+)")
    name = find(r"名字[:：]\s*(.+?)\s*编号")
    number = find(r"编号[:：]\s*(\d+)")
    rule = find(r"规则[:：]\s*([^\s]+)")

    if not name:
        name = find(r"名字[:：]\s*(.+)")

    if not group or not name or not number or not rule:
        return await m.reply("❌ 表单解析失败，请检查格式")

    new_title = f"{group}{number}-{rule}{name}"

    try:
        await bot.set_chat_title(m.chat.id, new_title)

        try:
            await m.answer(f"担保规则写入成功\n{new_title}")
        except Exception as e:
            await m.reply("⚠️ 群名已修改，但机器人没有权限发送消息")
            print("rename_group send failed:", e)

    except Exception as e:
        await m.reply("❌ 修改群名失败，请检查机器人权限")
        print("rename_group error:", e)

# ================= AUTO POST =================
@dp.message(lambda m: m.text and is_cmd(m, "/addpost"))
async def add_post_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    body = m.text[len("/addpost"):].strip()
    data = parse_block_fields(body)

    interval = data.get("interval")
    text = data.get("text")
    image = data.get("image")
    buttons = data.get("buttons")

    if not interval or not interval.isdigit():
        return await m.reply("❌ interval phải là số phút\nVí dụ: interval: 30")

    if not text:
        return await m.reply("❌ thiếu text")

    add_scheduled_post(
        chat_id=m.chat.id,
        interval_min=int(interval),
        text=text,
        image=image,
        buttons=buttons
    )

    log_action(m.from_user.id, "add_post", m.chat.id)
    await m.reply(f"✅ Đã tạo bài tự động mỗi {interval} phút")

@dp.message(lambda m: m.text and is_cmd(m, "/editpost"))
async def edit_post_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.reply(
            "Cách dùng:\n"
            "/editpost 1\n"
            "interval: 60\n"
            "text: Nội dung mới\n"
            "image: https://img.com/new.jpg\n"
            "buttons: Nút 1|https://a.com;Nút 2|https://b.com"
        )

    head = parts[1].strip().split(maxsplit=1)
    if not head or not head[0].isdigit():
        return await m.reply("❌ Thiếu ID bài viết\nVí dụ: /editpost 1")

    post_id = int(head[0])
    body = parts[1].replace(str(post_id), "", 1).strip()

    if not body:
        return await m.reply(
            "Cách dùng:\n"
            "/editpost 1\n"
            "interval: 60\n"
            "text: Nội dung mới\n"
            "image: https://img.com/new.jpg\n"
            "buttons: Nút 1|https://a.com;Nút 2|https://b.com"
        )

    data = parse_block_fields(body)
    interval = data.get("interval")
    text = data.get("text")
    image = data.get("image")
    buttons = data.get("buttons")

    if interval is not None and not interval.isdigit():
        return await m.reply("❌ interval phải là số phút")

    old = get_scheduled_post(post_id)
    if not old:
        return await m.reply("❌ Không tìm thấy bài viết tự động")

    new_interval = int(interval) if interval else old[2]
    new_text = text if text is not None else old[3]
    new_image = image if image is not None else old[4]
    new_buttons = buttons if buttons is not None else old[5]

    ok = update_scheduled_post(
        post_id=post_id,
        interval_min=new_interval,
        text=new_text,
        image=new_image,
        buttons=new_buttons
    )

    if not ok:
        return await m.reply("❌ Cập nhật thất bại")

    log_action(m.from_user.id, "edit_post", m.chat.id)
    await m.reply(f"✅ Đã cập nhật bài tự động ID: {post_id}")

@dp.message(lambda m: m.text and is_cmd(m, "/posts"))
async def list_posts_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    posts = get_scheduled_posts()
    if not posts:
        return await m.reply("Chưa có bài tự động nào")

    text = "📋 Danh sách bài tự động:\n\n"
    for post_id, chat_id, interval_min, post_text, image, buttons, enabled, next_run in posts:
        text += f"• ID: {post_id} | Chat: {chat_id} | {interval_min} phút\n"

    await m.reply(text)

@dp.message(lambda m: m.text and is_cmd(m, "/showpost"))
async def show_post_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().split()[0].isdigit():
        return await m.reply("Cách dùng: /showpost 1")

    post_id = int(parts[1].strip().split()[0])
    row = get_scheduled_post(post_id)

    if not row:
        return await m.reply("❌ Không tìm thấy bài viết")

    pid, chat_id, interval_min, text_content, image, buttons, enabled, next_run = row

    msg = (
        f"📌 ID: {pid}\n"
        f"💬 Chat: {chat_id}\n"
        f"⏱ Interval: {interval_min} phút\n"
        f"✅ Enabled: {enabled}\n"
        f"📝 Text: {text_content}\n"
        f"🖼 Image: {image or 'None'}\n"
        f"🔘 Buttons: {buttons or 'None'}\n"
        f"⏭ Next run: {next_run}"
    )

    await m.reply(msg)

@dp.message(lambda m: m.text and is_cmd(m, "/delpost"))
async def del_post_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    parts = m.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        return await m.reply("Cách dùng: /delpost 1")

    post_id = int(parts[1])
    remove_scheduled_post(post_id)
    await m.reply(f"✅ Đã xoá bài tự động ID: {post_id}")

# ================= PIN MESSAGE =================
@dp.message(lambda m: m.text and is_cmd(m, "ghimmes", "/ghimmes"))
async def pin_message_cmd(m: types.Message):
    if get_admin(m.from_user.id) not in ("super", "admin"):
        return await m.reply("❌ 无权限")

    if not m.reply_to_message:
        return await m.reply("❌ Hãy reply vào bài viết cần ghim rồi gõ ghimmes")

    try:
        await bot.pin_chat_message(
            chat_id=m.chat.id,
            message_id=m.reply_to_message.message_id,
            disable_notification=False
        )
        await m.reply("✅ Đã ghim bài viết")
    except Exception as e:
        await m.reply("❌ Bot không có quyền ghim bài viết")
        print("pin_message_cmd error:", e)

# ================= GENERAL TEXT: KEY / ANTI / AI =================
@dp.message()
async def handle_general_text(m: types.Message):
    if not m.text:
        return

    if m.text.startswith("/"):
        return

    # 1) Key reply trước
    match = find_keyword_match(m.text)
    if match:
        await send_keyword_reply(m, match)
        return

    # 2) Anti scam: xoá link
    if re.search(r"(http|t.me|www|\.com)", m.text.lower()):
        try:
            await m.delete()
        except Exception as e:
            print("anti delete failed:", e)
        return

    # 3) AI
    if m.chat.type != "private" and "ai" not in m.text.lower():
        return

    prompt = m.text
    if prompt.lower().startswith("ai "):
        prompt = prompt[3:]
    elif prompt.lower() == "ai":
        prompt = ""

    reply = await ask_ai(m.from_user.id, prompt)
    await m.reply(reply)

# ================= DASHBOARD =================
@app.get("/dashboard")
def dashboard():
    return FileResponse("frontend/index.html")

@app.get("/admin/list")
async def admin_list():
    return {"data": get_all_admins()}

@app.get("/admin/logs")
async def logs():
    return {"data": get_logs()}

@app.get("/admin/groups")
async def groups():
    return {"data": get_groups()}

# ================= WEBHOOK =================
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
