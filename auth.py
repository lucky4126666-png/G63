from fastapi import APIRouter
import sqlite3

router = APIRouter()

@router.post("/register")
def register(data: dict):
    conn = sqlite3.connect("data.db")
    c = conn.cursor()

    c.execute("INSERT INTO users(username,password) VALUES (?,?)",
              (data["username"], data["password"]))
    conn.commit()

    return {"ok": True}

@router.post("/login")
def login(data: dict):
    conn = sqlite3.connect("data.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE username=? AND password=?",
              (data["username"], data["password"]))

    user = c.fetchone()

    if user:
        return {"ok": True}
    return {"ok": False}
