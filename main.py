import os
import asyncio
import sqlite3

from fastapi import FastAPI, Request
from dotenv import load_dotenv

from db import init_db
from auth import router as auth_router
from bot_manager import send
from ai_service import ask_ai

load_dotenv()

app = FastAPI()
app.include_router(auth_router)

init_db()

# ===== API =====

@app.post("/send")
async def send_msg(data: dict):
    await send(data["token"], data["chat_id"], data["text"])
    return {"ok": True}

@app.post("/ai")
async def ai(data: dict):
    reply = await ask_ai(data["text"])
    return {"reply": reply}

@app.get("/")
def home():
    return {"status":"SaaS running"}
