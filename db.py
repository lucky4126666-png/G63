import psycopg2
from psycopg2 import pool
from config import DATABASE_URL

db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, DATABASE_URL)

def get_conn():
    return db_pool.getconn()

def release_conn(conn):
    db_pool.putconn(conn)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS keywords (
        id SERIAL PRIMARY KEY,
        trigger TEXT UNIQUE,
        response TEXT
    );
    """)

    conn.commit()
    release_conn(conn)
