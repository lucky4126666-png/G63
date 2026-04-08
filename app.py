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
