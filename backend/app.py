import asyncio
from fastapi import FastAPI
from db import get_conn
from bot_engine import start_bot

app = FastAPI()

# ===== CREATE USER =====
@app.post("/register")
def register(username: str, password: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO users (username, password) VALUES (%s,%s)",
        (username, password)
    )

    conn.commit()
    conn.close()

    return {"ok": True}

# ===== CREATE BOT =====
@app.post("/create-bot")
def create_bot(user_id: int, token: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO bots (user_id, token) VALUES (%s,%s) RETURNING id",
        (user_id, token)
    )

    bot_id = cur.fetchone()[0]

    conn.commit()
    conn.close()

    asyncio.create_task(start_bot(bot_id, token))

    return {"bot_id": bot_id}

# ===== ADD KEYWORD =====
@app.post("/add-key")
def add_key(bot_id: int, trigger: str, response: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO keywords (bot_id, trigger, response) VALUES (%s,%s,%s)",
        (bot_id, trigger, response)
    )

    conn.commit()
    conn.close()

    return {"ok": True}

# ===== START ALL BOT =====
@app.on_event("startup")
async def startup():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, token FROM bots")
    bots = cur.fetchall()
    conn.close()

    for b in bots:
        asyncio.create_task(start_bot(b[0], b[1]))

@app.get("/")
def home():
    return {"status": "ok"}
