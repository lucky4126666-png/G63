import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

from core.db import connect_db
from core.bot_manager import load_all_bots

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 G63 SYSTEM STARTING...")

    await connect_db()
    await load_all_bots()

    print("✅ ALL BOTS ONLINE")

    yield

    print("🛑 SYSTEM SHUTDOWN")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def home():
    return {"status": "G63 VIP RUNNING"}
