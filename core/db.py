import asyncpg
import os

pool = None

async def connect_db():
    global pool
    pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=1,
        max_size=10
    )
