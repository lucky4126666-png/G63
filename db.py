import psycopg2, os

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

def query(q, v=None):
    cur.execute(q, v or ())
    conn.commit()
    return cur.fetchall() if cur.description else None
