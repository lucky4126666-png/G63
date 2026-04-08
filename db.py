import sqlite3
import time

DB_NAME = "data.db"

def get_conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        role TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        name TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS keywords (
        key TEXT PRIMARY KEY,
        reply TEXT,
        image TEXT,
        buttons TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        chat_id INTEGER,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        interval_min INTEGER,
        text TEXT,
        image TEXT,
        buttons TEXT,
        enabled INTEGER DEFAULT 1,
        next_run INTEGER
    )
    """)

    conn.commit()
    conn.close()

def add_admin(user_id, role="admin"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO admins(user_id, role)
    VALUES (?,?)
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
    r = cur.fetchone()
    conn.close()
    return r[0] if r else None

def get_all_admins():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admins")
    rows = cur.fetchall()
    conn.close()
    return rows

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
    cur.execute("SELECT * FROM groups")
    rows = cur.fetchall()
    conn.close()
    return rows

def add_keyword(key, reply, image=None, buttons=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO keywords(key, reply, image, buttons)
    VALUES (?,?,?,?)
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

def get_keyword(key):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT key, reply, image, buttons
    FROM keywords
    WHERE key=?
    """, (key,))
    row = cur.fetchone()
    conn.close()
    return row

def remove_keyword(key):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM keywords WHERE key=?", (key,))
    conn.commit()
    conn.close()

def log_action(user_id, action, chat_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO logs(user_id, action, chat_id) VALUES (?,?,?)",
        (user_id, action, chat_id)
    )
    conn.commit()
    conn.close()

def get_logs():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

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
    r = cur.fetchone()
    conn.close()
    return r[0] if r else None

def add_scheduled_post(chat_id, interval_min, text, image=None, buttons=None):
    conn = get_conn()
    cur = conn.cursor()
    next_run = int(time.time()) + int(interval_min) * 60
    cur.execute("""
    INSERT INTO scheduled_posts(chat_id, interval_min, text, image, buttons, enabled, next_run)
    VALUES (?,?,?,?,?,?,?)
    """, (chat_id, interval_min, text, image, buttons, 1, next_run))
    conn.commit()
    conn.close()

def get_scheduled_posts():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, chat_id, interval_min, text, image, buttons, enabled, next_run
    FROM scheduled_posts
    WHERE enabled=1
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_due_scheduled_posts(now_ts):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, chat_id, interval_min, text, image, buttons, enabled, next_run
    FROM scheduled_posts
    WHERE enabled=1 AND next_run <= ?
    """, (now_ts,))
    rows = cur.fetchall()
    conn.close()
    return rows

def update_scheduled_post_next_run(post_id, next_run):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    UPDATE scheduled_posts
    SET next_run=?
    WHERE id=?
    """, (next_run, post_id))
    conn.commit()
    conn.close()

def update_scheduled_post(post_id, interval_min=None, text=None, image=None, buttons=None, enabled=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT chat_id, interval_min, text, image, buttons, enabled
    FROM scheduled_posts
    WHERE id=?
    """, (post_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    chat_id, old_interval, old_text, old_image, old_buttons, old_enabled = row

    new_interval = interval_min if interval_min is not None else old_interval
    new_text = text if text is not None else old_text
    new_image = image if image is not None else old_image
    new_buttons = buttons if buttons is not None else old_buttons
    new_enabled = enabled if enabled is not None else old_enabled

    next_run = int(time.time()) + int(new_interval) * 60

    cur.execute("""
    UPDATE scheduled_posts
    SET interval_min=?, text=?, image=?, buttons=?, enabled=?, next_run=?
    WHERE id=?
    """, (new_interval, new_text, new_image, new_buttons, new_enabled, next_run, post_id))

    conn.commit()
    conn.close()
    return True

def get_scheduled_post(post_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, chat_id, interval_min, text, image, buttons, enabled, next_run
    FROM scheduled_posts
    WHERE id=?
    """, (post_id,))
    row = cur.fetchone()
    conn.close()
    return row

def remove_scheduled_post(post_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM scheduled_posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
