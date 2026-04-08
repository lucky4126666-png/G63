def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # memory
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        content TEXT
    )
    """)

    # settings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()


def get_setting(key):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()

    return row[0] if row else None


def set_setting(key, value):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO settings(key,value)
    VALUES (?,?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, value))

    conn.commit()
    conn.close()
