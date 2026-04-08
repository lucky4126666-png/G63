import sqlite3

def get_conn():
    return sqlite3.connect("data.db")

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trigger TEXT UNIQUE,
        response TEXT
    );
    """)

    conn.commit()
    conn.close()
