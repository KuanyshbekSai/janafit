import aiosqlite
from datetime import datetime
from typing import Optional, Dict, Any, List
from config import settings

async def init_db():
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                has_access BOOLEAN DEFAULT 0,
                access_granted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT UNIQUE,
                user_id INTEGER,
                amount INTEGER,
                currency TEXT DEFAULT 'KZT',
                provider TEXT,
                status TEXT DEFAULT 'pending',
                receipt_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                user_id INTEGER,
                day INTEGER,
                completed BOOLEAN DEFAULT 1,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                weight REAL,
                waist REAL,
                hips REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                dish_name TEXT,
                calories INTEGER,
                protein REAL,
                fats REAL,
                carbs REAL,
                advice TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()

async def get_or_create_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> Dict[str, Any]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)

        await db.execute(
            "INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, last_name)
        )
        await db.commit()

        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row)

async def check_user_access(user_id: int) -> bool:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT has_access FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return True
            return False

async def grant_user_access(user_id: int):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET has_access = 1, access_granted_at = ? WHERE user_id = ?",
            (now, user_id)
        )
        await db.commit()

async def create_payment(invoice_id: str, user_id: int, amount: int, provider: str, receipt_file_id: Optional[str] = None) -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO payments (invoice_id, user_id, amount, provider, status, receipt_file_id)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (invoice_id, user_id, amount, provider, receipt_file_id)
        )
        await db.commit()
        return cursor.lastrowid

async def mark_payment_success(invoice_id: str) -> Optional[int]:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id, status FROM payments WHERE invoice_id = ?", (invoice_id,)) as cursor:
            payment = await cursor.fetchone()
            if not payment:
                return None
            user_id = payment["user_id"]

        await db.execute(
            "UPDATE payments SET status = 'success', updated_at = ? WHERE invoice_id = ?",
            (now, invoice_id)
        )
        await db.execute(
            "UPDATE users SET has_access = 1, access_granted_at = ? WHERE user_id = ?",
            (now, user_id)
        )
        await db.commit()
        return user_id

async def get_payment_by_id(payment_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def add_ai_message(user_id: int, role: str, content: str):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO ai_chats (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )
        await db.commit()

async def get_recent_ai_history(user_id: int, limit: int = 10) -> List[Dict[str, str]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role, content FROM ai_chats WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            # return in chronological order
            return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

async def get_sales_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE has_access = 1") as c:
            active_students = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE status = 'success'") as c:
            success_payments, total_revenue = await c.fetchone()
        async with db.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'") as c:
            pending_payments = (await c.fetchone())[0]

        return {
            "total_users": total_users,
            "active_students": active_students,
            "success_payments": success_payments,
            "total_revenue": total_revenue,
            "pending_payments": pending_payments
        }

async def save_user_progress(user_id: int, day: int, completed: bool):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        if completed:
            await db.execute(
                "INSERT OR REPLACE INTO user_progress (user_id, day, completed) VALUES (?, ?, 1)",
                (user_id, day)
            )
        else:
            await db.execute(
                "DELETE FROM user_progress WHERE user_id = ? AND day = ?",
                (user_id, day)
            )
        await db.commit()

async def get_user_progress(user_id: int) -> List[int]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT day FROM user_progress WHERE user_id = ? AND completed = 1", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def save_user_measurement(user_id: int, weight: float, waist: float, hips: float):
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_measurements (user_id, weight, waist, hips) VALUES (?, ?, ?, ?)",
            (user_id, weight, waist, hips)
        )
        await db.commit()

async def get_user_measurements(user_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT weight, waist, hips, created_at FROM user_measurements WHERE user_id = ? ORDER BY id ASC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def save_user_meal(user_id: int, dish_name: str, calories: int, protein: float, fats: float, carbs: float, advice: str) -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO user_meals (user_id, dish_name, calories, protein, fats, carbs, advice)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, dish_name, calories, protein, fats, carbs, advice)
        )
        await db.commit()
        return cursor.lastrowid

async def get_user_meals(user_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, dish_name, calories, protein, fats, carbs, advice, created_at FROM user_meals WHERE user_id = ? ORDER BY id DESC LIMIT 10",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


