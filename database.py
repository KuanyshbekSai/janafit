import aiosqlite
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from config import settings

def ensure_db_dir():
    try:
        dir_name = os.path.dirname(settings.DB_PATH)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
    except Exception:
        pass

_db_initialized = False

async def ensure_db_ready():
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True

async def init_db():
    global _db_initialized
    ensure_db_dir()
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
                omega3_score INTEGER DEFAULT 25,
                aojiru_score INTEGER DEFAULT 30,
                vitamins_score INTEGER DEFAULT 50,
                recommendation_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                gender TEXT DEFAULT 'female',
                age INTEGER DEFAULT 25,
                height REAL DEFAULT 168.0,
                current_weight REAL DEFAULT 65.0,
                target_weight REAL DEFAULT 58.0,
                waist REAL DEFAULT 72.0,
                hips REAL DEFAULT 98.0,
                goal TEXT DEFAULT 'weight_loss',
                activity_level TEXT DEFAULT 'medium',
                daily_calories_target INTEGER DEFAULT 1600,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Попытка добавить колонки, если таблица уже существовала
        for col in [
            "ALTER TABLE user_meals ADD COLUMN omega3_score INTEGER DEFAULT 25",
            "ALTER TABLE user_meals ADD COLUMN aojiru_score INTEGER DEFAULT 30",
            "ALTER TABLE user_meals ADD COLUMN vitamins_score INTEGER DEFAULT 50",
            "ALTER TABLE user_meals ADD COLUMN recommendation_json TEXT",
            "ALTER TABLE user_profiles ADD COLUMN phone TEXT DEFAULT ''",
            "ALTER TABLE user_profiles ADD COLUMN chest REAL DEFAULT 92.0",
            "ALTER TABLE user_profiles ADD COLUMN start_weight REAL DEFAULT 0.0",
            "ALTER TABLE user_profiles ADD COLUMN start_waist REAL DEFAULT 0.0",
            "ALTER TABLE user_profiles ADD COLUMN start_hips REAL DEFAULT 0.0",
            "ALTER TABLE user_profiles ADD COLUMN start_chest REAL DEFAULT 0.0",
            "ALTER TABLE user_profiles ADD COLUMN is_registered INTEGER DEFAULT 0",
            "ALTER TABLE user_profiles ADD COLUMN photo_before TEXT DEFAULT ''",
            "ALTER TABLE user_profiles ADD COLUMN photo_after TEXT DEFAULT ''",
            "ALTER TABLE user_profiles ADD COLUMN completed_lessons TEXT DEFAULT '[]'",
            "ALTER TABLE user_profiles ADD COLUMN burned_calories INTEGER DEFAULT 0",
            "ALTER TABLE user_profiles ADD COLUMN rating_points INTEGER DEFAULT 0"
        ]:
            try:
                await db.execute(col)
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
    _db_initialized = True

async def get_or_create_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> Dict[str, Any]:
    await ensure_db_ready()
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
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT has_access FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return True
            return False

async def grant_user_access(user_id: int):
    await ensure_db_ready()
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET has_access = 1, access_granted_at = ? WHERE user_id = ?",
            (now, user_id)
        )
        await db.commit()

async def revoke_user_access(user_id: int):
    """Отзывает доступ к марафону (для Саппорта при возврате средств)."""
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET has_access = 0 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

async def get_admin_dashboard_stats() -> Dict[str, Any]:
    """Сводная статистика для Главного Дашборда (Аналитика)."""
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0] or 0

        async with db.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')") as cur:
            new_today = (await cur.fetchone())[0] or 0

        async with db.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')") as cur:
            new_week = (await cur.fetchone())[0] or 0

        async with db.execute("SELECT COUNT(*) FROM users WHERE has_access = 1") as cur:
            paid_users = (await cur.fetchone())[0] or 0

        async with db.execute("SELECT SUM(amount), COUNT(*) FROM payments WHERE status = 'success'") as cur:
            row = await cur.fetchone()
            total_revenue = row[0] or 0
            successful_payments = row[1] or 0

        conversion = round((paid_users / total_users * 100), 1) if total_users > 0 else 0.0

        return {
            "total_users": total_users,
            "new_today": new_today,
            "new_week": new_week,
            "paid_users": paid_users,
            "free_users": max(0, total_users - paid_users),
            "successful_payments": successful_payments,
            "total_revenue": total_revenue,
            "conversion_rate": conversion
        }

async def get_admin_users(filter_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Список пользователей для модуля CRM с профилем, телефоном и статистикой."""
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT
                u.user_id, u.username, u.first_name, u.last_name,
                COALESCE(p.phone, u.phone, '') AS phone,
                u.has_access, u.access_granted_at, u.created_at,
                p.gender, p.age, p.height, p.current_weight, p.target_weight,
                p.start_weight, p.waist, p.hips, p.goal, p.daily_calories_target,
                p.is_registered, p.burned_calories, p.rating_points,
                p.completed_lessons,
                (SELECT COUNT(*) FROM user_progress up WHERE up.user_id = u.user_id AND up.completed = 1) AS completed_workouts,
                (SELECT COUNT(*) FROM user_meals um WHERE um.user_id = u.user_id) AS meals_count
            FROM users u
            LEFT JOIN user_profiles p ON u.user_id = p.user_id
        """
        params = []
        if filter_type == "paid":
            query += " WHERE u.has_access = 1"
        elif filter_type == "free":
            query += " WHERE u.has_access = 0"
        query += " ORDER BY u.created_at DESC LIMIT ?"
        params.append(limit)

        async with db.execute(query, tuple(params)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_broadcast_user_ids(filter_type: str = "all") -> List[int]:
    """Получение ID пользователей для рассылок (все, оплатившие, неоплатившие)."""
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        if filter_type == "paid":
            query = "SELECT user_id FROM users WHERE has_access = 1"
        elif filter_type == "free":
            query = "SELECT user_id FROM users WHERE has_access = 0"
        else:
            query = "SELECT user_id FROM users"
        async with db.execute(query) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

async def create_payment(invoice_id: str, user_id: int, amount: int, provider: str, receipt_file_id: Optional[str] = None) -> int:
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO payments (invoice_id, user_id, amount, provider, status, receipt_file_id)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (invoice_id, user_id, amount, provider, receipt_file_id)
        )
        await db.commit()
        return cursor.lastrowid

async def mark_payment_success(invoice_id: str) -> Optional[int]:
    await ensure_db_ready()
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
    await ensure_db_ready()
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
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT day FROM user_progress WHERE user_id = ? AND completed = 1", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def save_user_measurement(user_id: int, weight: float, waist: float, hips: float):
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_measurements (user_id, weight, waist, hips) VALUES (?, ?, ?, ?)",
            (user_id, weight, waist, hips)
        )
        await db.commit()

async def get_user_measurements(user_id: int) -> List[Dict[str, Any]]:
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT weight, waist, hips, created_at FROM user_measurements WHERE user_id = ? ORDER BY id ASC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def save_user_meal(
    user_id: int,
    dish_name: str,
    calories: int,
    protein: float,
    fats: float,
    carbs: float,
    advice: str,
    omega3_score: int = 25,
    aojiru_score: int = 30,
    vitamins_score: int = 50,
    recommendation_json: str = None
) -> int:
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO user_meals (
                user_id, dish_name, calories, protein, fats, carbs, advice,
                omega3_score, aojiru_score, vitamins_score, recommendation_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, dish_name, calories, protein, fats, carbs, advice, omega3_score, aojiru_score, vitamins_score, recommendation_json)
        )
        await db.commit()
        return cursor.lastrowid

async def get_user_meals(user_id: int) -> List[Dict[str, Any]]:
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT id, dish_name, calories, protein, fats, carbs, advice,
                      omega3_score, aojiru_score, vitamins_score, recommendation_json, created_at
               FROM user_meals WHERE user_id = ? ORDER BY id DESC LIMIT 20""",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def save_user_profile(
    user_id: int,
    gender: str = "female",
    age: int = 25,
    height: float = 168.0,
    current_weight: float = 65.0,
    target_weight: float = 58.0,
    waist: float = 72.0,
    hips: float = 98.0,
    goal: str = "weight_loss",
    activity_level: str = "medium",
    daily_calories_target: int = 1600,
    phone: str = "",
    chest: float = 92.0,
    is_registered: int = 1,
    photo_before: Optional[str] = None,
    photo_after: Optional[str] = None,
    completed_lessons: Optional[str] = None,
    burned_calories: Optional[int] = None,
    rating_points: Optional[int] = None,
    username: Optional[str] = None,
    first_name: Optional[str] = None
):
    await ensure_db_ready()
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Убедимся, что запись в users существует и обновим телефон/имя
        await db.execute(
            """INSERT INTO users (user_id, username, first_name, phone)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 phone = CASE WHEN excluded.phone != '' THEN excluded.phone ELSE users.phone END,
                 username = COALESCE(excluded.username, users.username),
                 first_name = COALESCE(excluded.first_name, users.first_name)""",
            (user_id, username, first_name, phone or "")
        )

        # Проверим, был ли пользователь уже зарегистрирован (чтобы не менять зафиксированные пол, цель и стартовые замеры)
        async with db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)) as cur:
            existing = await cur.fetchone()

        if existing and existing["is_registered"]:
            locked_gender = existing["gender"] or gender
            locked_age = existing["age"] or age
            locked_height = existing["height"] or height
            locked_goal = existing["goal"] or goal
            locked_phone = existing["phone"] if existing["phone"] else phone
            start_w = existing["start_weight"] if existing["start_weight"] else current_weight
            start_waist = existing["start_waist"] if existing["start_waist"] else waist
            start_hips = existing["start_hips"] if existing["start_hips"] else hips
            start_chest = existing["start_chest"] if existing["start_chest"] else chest
            p_before = photo_before if photo_before is not None else (existing["photo_before"] or "")
            p_after = photo_after if photo_after is not None else (existing["photo_after"] or "")
            c_lessons = completed_lessons if completed_lessons is not None else (existing["completed_lessons"] or "[]")
            b_cal = burned_calories if burned_calories is not None else (existing["burned_calories"] or 0)
            r_pts = rating_points if rating_points is not None else (existing["rating_points"] or 0)
        else:
            locked_gender = gender
            locked_age = age
            locked_height = height
            locked_goal = goal
            locked_phone = phone
            start_w = current_weight
            start_waist = waist
            start_hips = hips
            start_chest = chest
            p_before = photo_before or ""
            p_after = photo_after or ""
            c_lessons = completed_lessons or "[]"
            b_cal = burned_calories or 0
            r_pts = rating_points or 150

        await db.execute("""
            INSERT INTO user_profiles (
                user_id, gender, age, height, current_weight, target_weight,
                waist, hips, chest, start_weight, start_waist, start_hips, start_chest,
                goal, activity_level, daily_calories_target, phone, is_registered,
                photo_before, photo_after, completed_lessons, burned_calories, rating_points, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                gender=excluded.gender,
                age=excluded.age,
                height=excluded.height,
                current_weight=excluded.current_weight,
                target_weight=excluded.target_weight,
                waist=excluded.waist,
                hips=excluded.hips,
                chest=excluded.chest,
                start_weight=excluded.start_weight,
                start_waist=excluded.start_waist,
                start_hips=excluded.start_hips,
                start_chest=excluded.start_chest,
                goal=excluded.goal,
                activity_level=excluded.activity_level,
                daily_calories_target=excluded.daily_calories_target,
                phone=excluded.phone,
                is_registered=excluded.is_registered,
                photo_before=excluded.photo_before,
                photo_after=excluded.photo_after,
                completed_lessons=excluded.completed_lessons,
                burned_calories=excluded.burned_calories,
                rating_points=excluded.rating_points,
                updated_at=excluded.updated_at
        """, (
            user_id, locked_gender, locked_age, locked_height, current_weight, target_weight,
            waist, hips, chest, start_w, start_waist, start_hips, start_chest,
            locked_goal, activity_level, daily_calories_target, locked_phone, is_registered,
            p_before, p_after, c_lessons, b_cal, r_pts, now
        ))
        await db.commit()

async def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_app_settings(key: str = "cms_config") -> Dict[str, Any]:
    import json
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT value_json FROM app_settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    return {}
            return {}

async def save_app_settings(value: Dict[str, Any], key: str = "cms_config"):
    import json
    await ensure_db_ready()
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """INSERT INTO app_settings (key, value_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at""",
            (key, json.dumps(value, ensure_ascii=False), now)
        )
        await db.commit()

async def get_leaderboard(limit: int = 30) -> List[Dict[str, Any]]:
    await ensure_db_ready()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT
                u.user_id,
                COALESCE(NULLIF(u.first_name, ''), NULLIF(u.username, ''), 'Атлет #' || substr(cast(u.user_id as text), -4)) AS display_name,
                COALESCE(p.rating_points, 0) AS rating_points,
                COALESCE(p.burned_calories, 0) AS burned_calories,
                (SELECT COUNT(*) FROM user_progress up WHERE up.user_id = u.user_id AND up.completed = 1) AS workouts_done
            FROM users u
            LEFT JOIN user_profiles p ON u.user_id = p.user_id
            ORDER BY rating_points DESC, workouts_done DESC
            LIMIT ?
        """
        async with db.execute(query, (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]




