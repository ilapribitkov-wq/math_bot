import aiosqlite
import datetime
import time

DB_PATH = "users.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                free_attempts INTEGER DEFAULT 999,
                subscription_end DATE,
                trial_start DATE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS limits (
                user_id INTEGER PRIMARY KEY,
                last_message_time REAL,
                daily_count INTEGER DEFAULT 0,
                last_reset_date TEXT
            )
        """)
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT free_attempts, subscription_end, trial_start FROM users WHERE user_id = ?",
            (user_id,)
        )
        return await cursor.fetchone()

async def create_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        trial_start = datetime.datetime.now().strftime("%Y-%m-%d")
        await db.execute(
            "INSERT INTO users (user_id, free_attempts, trial_start) VALUES (?, 999, ?)",
            (user_id, trial_start)
        )
        await db.commit()

async def save_history(user_id, query, answer):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO history (user_id, query, answer) VALUES (?, ?, ?)",
            (user_id, query, answer)
        )
        await db.commit()

async def get_history(user_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT query, answer, created_at FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return await cursor.fetchall()

async def clear_history(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
        await db.commit()

async def activate_subscription(user_id, days=30):
    async with aiosqlite.connect(DB_PATH) as db:
        end_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        await db.execute(
            "UPDATE users SET subscription_end = ? WHERE user_id = ?",
            (end_date, user_id)
        )
        await db.commit()

async def check_flood(user_id, cooldown=3):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT last_message_time FROM limits WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        now = time.time()
        if row:
            last_time = row[0]
            if now - last_time < cooldown:
                return False
        await db.execute(
            "INSERT INTO limits (user_id, last_message_time) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_message_time = ?",
            (user_id, now, now)
        )
        await db.commit()
        return True

async def check_daily_limit(user_id, limit=200):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT daily_count, last_reset_date FROM limits WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            count, reset_date = row
            if reset_date != today:
                count = 0
                reset_date = today
            if count >= limit:
                return False
            await db.execute(
                "UPDATE limits SET daily_count = ? WHERE user_id = ?",
                (count + 1, user_id)
            )
        else:
            await db.execute(
                "INSERT INTO limits (user_id, daily_count, last_reset_date) VALUES (?, ?, ?)",
                (user_id, 1, today)
            )
        await db.commit()
        return True
