import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, List
from config import settings

logger = logging.getLogger(__name__)

async def _post_gas(payload: Dict[str, Any]) -> bool:
    gas_url = getattr(settings, "GAS_WEBAPP_URL", "")
    if not gas_url:
        return False

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(gas_url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    return True
                else:
                    logger.warning(f"GAS returned status {resp.status}")
    except Exception as e:
        logger.warning(f"GAS sync error (non-fatal): {e}")
    return False

def fire_and_forget(coro):
    """Запускает фоновую задачу, не блокируя основной поток ответа пользователю."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(coro)
        else:
            asyncio.run(coro)
    except Exception:
        pass

async def sync_user_to_gas(
    user_id: int,
    name: str = "",
    username: str = "",
    has_access: bool = False,
    goal: str = "",
    height: float = 168.0,
    current_weight: float = 65.0,
    target_weight: float = 58.0,
    waist: float = 72.0,
    hips: float = 98.0,
    workouts_completed: int = 0,
    meals_logged: int = 0
):
    await _post_gas({
        "action": "syncUser",
        "user_id": user_id,
        "name": name,
        "username": username,
        "has_access": has_access,
        "goal": goal,
        "height": height,
        "current_weight": current_weight,
        "target_weight": target_weight,
        "waist": waist,
        "hips": hips,
        "workouts_completed": workouts_completed,
        "meals_logged": meals_logged
    })

async def log_payment_to_gas(inv_id: str, user_id: int, sum_amount: int, status: str = "PAID"):
    await _post_gas({
        "action": "savePayment",
        "inv_id": inv_id,
        "user_id": user_id,
        "sum": sum_amount,
        "status": status,
        "system": "Robokassa"
    })

async def log_meal_to_gas(
    user_id: int,
    dish_name: str,
    input_type: str, # "Фото" или "Голос"
    calories: int,
    protein: float,
    fats: float,
    carbs: float,
    health_score: float = 9.0,
    advice: str = ""
):
    await _post_gas({
        "action": "logMeal",
        "user_id": user_id,
        "dish_name": dish_name,
        "input_type": input_type,
        "calories": calories,
        "protein": protein,
        "fats": fats,
        "carbs": carbs,
        "health_score": health_score,
        "advice": advice
    })

async def log_workout_to_gas(user_id: int, day: int):
    await _post_gas({
        "action": "logWorkout",
        "user_id": user_id,
        "day": day
    })

async def fetch_lessons_from_gas() -> Optional[List[Dict[str, Any]]]:
    gas_url = getattr(settings, "GAS_WEBAPP_URL", "")
    if not gas_url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{gas_url}?action=getLessons", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "ok":
                        return data.get("lessons", [])
    except Exception as e:
        logger.warning(f"Error fetching lessons from GAS: {e}")
    return None
