import sqlite3

DB_NAME = "data.db"


# ===== CONNECT =====
def get_conn():
    return sqlite3.connect(DB_NAME)


# ===== INIT =====
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # ===== ADMINS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        role TEXT
    )
    """)

    # ===== LOGS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        chat_id INTEGER,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ===== GROUPS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        name TEXT
    )
    """)

    # ===== SETTINGS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()


# ================= ADMIN =================

def add_admin(user_id, role="admin"):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO admins(user_id, role)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET role=excluded.role
    """, (user_id, role))

    conn.commit()
    conn.close()


def remove_admin(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM admins WHERE user_id=?", (user_id,))

    conn.commit()
    conn.close()


def get_admin(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT role FROM admins WHERE user_id=?", (user_id,))
    row = cur.fetchone()

    conn.close()
    return row[0] if row else None


def get_all_admins():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT user_id, role FROM admins")
    rows = cur.fetchall()

    conn.close()
    return rows


# ================= LOG =================

def log_action(user_id, action, chat_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO logs(user_id, action, chat_id) VALUES (?,?,?)",
        (user_id, action, chat_id)
    )

    conn.commit()
    conn.close()


def get_logs(limit=50):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT user_id, action, chat_id, time
    FROM logs
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))

    rows = cur.fetchall()

    conn.close()
    return rows


# ================= GROUP =================

def save_group(chat_id, name):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO groups(chat_id, name)
    VALUES (?,?)
    ON CONFLICT(chat_id) DO UPDATE SET name=excluded.name
    """, (chat_id, name))

    conn.commit()
    conn.close()


def get_groups():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT chat_id, name FROM groups")
    rows = cur.fetchall()

    conn.close()
    return rows


# ================= SETTINGS =================

def set_setting(key, value):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO settings(key, value)
    VALUES (?,?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, value))

    conn.commit()
    conn.close()


def get_setting(key):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()

    conn.close()
    return row[0] if row else None
    def add_keyword(key, reply, image=None, buttons=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS keywords (
        key TEXT PRIMARY KEY,
        reply TEXT,
        image TEXT,
        buttons TEXT
    )
    """)

    cur.execute("""
    INSERT INTO keywords(key, reply, image, buttons)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(key) DO UPDATE SET
    reply=excluded.reply,
    image=excluded.image,
    buttons=excluded.buttons
    """, (key, reply, image, buttons))

    conn.commit()
    conn.close()


def get_keywords():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT key, reply, image, buttons FROM keywords")
    rows = cur.fetchall()

    conn.close()
    return rows
