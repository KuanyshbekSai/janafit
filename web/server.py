import os
from fastapi import FastAPI, Request, Form, HTTPException, Header, UploadFile, File
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List

from config import settings
from database import (
    init_db,
    mark_payment_success,
    check_user_access,
    save_user_progress,
    get_user_progress,
    save_user_measurement,
    get_user_measurements,
    add_ai_message,
    get_recent_ai_history,
    save_user_meal,
    get_user_meals,
    save_user_profile,
    get_user_profile,
    create_payment,
    grant_user_access,
    revoke_user_access,
    get_admin_dashboard_stats,
    get_admin_users,
    get_broadcast_user_ids
)
import time
from services.robokassa import verify_robokassa_webhook, generate_robokassa_link
from services.security import validate_telegram_init_data
from services.ai_service import ask_ai_coach, analyze_food_photo, analyze_food_audio
from services.gas_sync import fire_and_forget, sync_user_to_gas, log_payment_to_gas, log_meal_to_gas, log_workout_to_gas, fetch_meals_from_gas, delete_meal_in_gas

app = FastAPI(title="Janafit Web & Webhook Server", redirect_slashes=False)

@app.on_event("startup")
async def on_startup():
    try:
        await init_db()
    except Exception as e:
        print(f"Warning: init_db on startup: {e}")

# Поиск директории шаблонов (совместимо как с локальным запуском, так и с Vercel Serverless)
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
candidates = [
    os.path.join(base_dir, "mini_app"),
    os.path.join(base_dir, "api", "mini_app"),
    os.path.join(os.path.dirname(__file__), "..", "mini_app"),
    os.path.join(os.path.dirname(__file__), "..", "api", "mini_app"),
    "/var/task/mini_app",
    "/var/task/api/mini_app",
    "mini_app",
    "api/mini_app"
]
valid_dirs = [d for d in candidates if os.path.isdir(d)]
if not valid_dirs:
    valid_dirs = [candidates[0]]
    try:
        os.makedirs(candidates[0], exist_ok=True)
    except Exception:
        pass

templates = Jinja2Templates(directory=valid_dirs)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    print(f"Server exception on {request.url.path}: {tb}")
    return HTMLResponse(
        f"<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'></head>"
        f"<body style='font-family:-apple-system,BlinkMacSystemFont,sans-serif;padding:20px;background:#0f172a;color:#f87171;'>"
        f"<h2 style='color:#ef4444;margin-bottom:8px;'>⚠️ Janafit Server Error (500)</h2>"
        f"<p style='color:#94a3b8;margin-top:0;'>Route: <code>{request.url.path}</code></p>"
        f"<pre style='background:#1e293b;padding:16px;border-radius:8px;color:#e2e8f0;overflow:auto;font-size:12px;line-height:1.5;'>{tb}</pre>"
        f"</body></html>",
        status_code=500
    )

class ProgressToggleRequest(BaseModel):
    day: int
    completed: bool
    init_data: Optional[str] = None
    user_id: Optional[int] = None

class MeasurementRequest(BaseModel):
    weight: float
    waist: float
    hips: float
    init_data: Optional[str] = None
    user_id: Optional[int] = None

class AIChatRequest(BaseModel):
    question: str
    init_data: Optional[str] = None
    user_id: Optional[int] = None

class ProfileRequest(BaseModel):
    gender: str = "female"
    age: int = 25
    height: float = 168.0
    current_weight: float = 65.0
    target_weight: float = 58.0
    waist: float = 72.0
    hips: float = 98.0
    goal: str = "weight_loss"
    activity_level: str = "medium"
    daily_calories_target: int = 1600
    init_data: Optional[str] = None
    user_id: Optional[int] = None

class SaveMealRequest(BaseModel):
    dish_name: str
    calories: int
    protein: float = 0.0
    fats: float = 0.0
    carbs: float = 0.0
    weight_g: Optional[int] = 300
    advice: Optional[str] = ""
    input_type: Optional[str] = "Фото"
    omega3_score: Optional[int] = 25
    aojiru_score: Optional[int] = 30
    vitamins_score: Optional[int] = 50
    user_id: Optional[int] = None
    init_data: Optional[str] = None

class DeleteMealRequest(BaseModel):
    meal_id: Optional[int] = None
    user_id: Optional[int] = None
    init_data: Optional[str] = None
    dish_name: Optional[str] = None
    calories: Optional[int] = None

def get_verified_user_id(init_data: Optional[str], fallback_user_id: Optional[int] = None) -> int:
    """
    Верифицирует Telegram initData. Если данные валидны и BOT_TOKEN задан, гарантирует подлинность Telegram User ID.
    Если BOT_TOKEN не задан в переменных окружения или данные локальные, безопасно использует fallback_user_id.
    """
    if init_data and settings.BOT_TOKEN:
        verified = validate_telegram_init_data(init_data, settings.BOT_TOKEN)
        if verified and "user" in verified:
            return int(verified["user"].get("id", 0))

    return fallback_user_id or 123456789

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": "Janafit Engine"}

@app.post("/robokassa/result", response_class=PlainTextResponse)
async def robokassa_result(
    OutSum: str = Form(...),
    InvId: str = Form(...),
    SignatureValue: str = Form(...),
    shp_user_id: str = Form(...)
):
    """
    Обработчик Robokassa ResultURL.
    Принимает подтверждение оплаты и мгновенно активирует доступ.
    """
    is_valid = verify_robokassa_webhook(OutSum, InvId, SignatureValue, shp_user_id)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid signature")

    user_id = await mark_payment_success(InvId)
    if user_id:
        fire_and_forget(log_payment_to_gas(InvId, int(shp_user_id), int(float(OutSum))))
        from bot_instance import bot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        invite_link = None
        if settings.PRIVATE_CHANNEL_ID:
            try:
                link_obj = await bot.create_chat_invite_link(
                    chat_id=settings.PRIVATE_CHANNEL_ID,
                    member_limit=1,
                    name=f"Janafit_Robo_{user_id}"
                )
                invite_link = link_obj.invite_link
            except Exception:
                pass

        buttons = []
        if invite_link:
            buttons.append([InlineKeyboardButton(text="💎 Вступить в Закрытый VIP-Канал", url=invite_link)])
        buttons.append([InlineKeyboardButton(text="▶️ Открыть тренировки в боте", callback_data="open_course")])
        buttons.append([InlineKeyboardButton(text="📱 Открыть Mini App плеер", web_app={"url": f"{settings.BASE_WEB_URL}/app"})])

        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"🎉 <b>Оплата {OutSum} ₸ успешно принята!</b>\n\nВам открыт доступ к курсу «{settings.COURSE_TITLE}».",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except Exception:
            pass

    return f"OK{InvId}"

@app.get("/payment/success", response_class=HTMLResponse)
async def payment_success_page(request: Request, InvId: str = "JF-ORDER", OutSum: str = "4990"):
    return templates.TemplateResponse(request=request, name="success.html", context={
        "inv_id": InvId,
        "out_sum": OutSum
    })

@app.get("/payment/fail", response_class=HTMLResponse)
async def payment_fail_page(request: Request):
    return templates.TemplateResponse(request=request, name="fail.html", context={})

class CreatePaymentRequest(BaseModel):
    user_id: Optional[int] = None
    init_data: Optional[str] = None

@app.post("/api/payment/create-robokassa")
async def api_create_robokassa_payment(payload: CreatePaymentRequest):
    """
    Генерирует ссылку Robokassa для оплаты курса из Mini App.
    """
    verified_id = get_verified_user_id(payload.init_data, payload.user_id)
    inv_id = str(int(time.time() * 10) % 2000000000)
    await create_payment(
        invoice_id=inv_id,
        user_id=verified_id,
        amount=settings.COURSE_PRICE,
        provider="robokassa"
    )
    pay_url = generate_robokassa_link(
        invoice_id=inv_id,
        amount=settings.COURSE_PRICE,
        description=f"Janafit Course Access #{inv_id}",
        user_id=verified_id
    )
    return {
        "status": "ok",
        "pay_url": pay_url,
        "invoice_id": inv_id,
        "amount": settings.COURSE_PRICE,
        "title": settings.COURSE_TITLE
    }

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/app", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/api", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/api/app", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/api/index.py", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def mini_app_view(request: Request, day: int = 1):
    return templates.TemplateResponse(request=request, name="index.html", context={
        "default_day": day,
        "course_title": settings.COURSE_TITLE
    })

# -------------------- ADMIN PANEL (По ТЗ) --------------------

@app.get("/admin", response_class=HTMLResponse)
@app.get("/api/admin", response_class=HTMLResponse)
async def admin_panel_view(request: Request):
    """Панель Администратора Janafit (Дашборд, CRM, Рассылки)."""
    return templates.TemplateResponse(request=request, name="admin.html", context={})

@app.get("/api/admin/stats")
async def api_admin_stats():
    stats = await get_admin_dashboard_stats()
    return stats

@app.get("/api/admin/users")
async def api_admin_users(filter: Optional[str] = "all", limit: int = 100):
    users = await get_admin_users(filter_type=filter, limit=limit)
    return users

class AdminToggleAccessRequest(BaseModel):
    user_id: int
    grant: bool

@app.post("/api/admin/toggle-access")
async def api_admin_toggle_access(payload: AdminToggleAccessRequest):
    if payload.grant:
        await grant_user_access(payload.user_id)
    else:
        await revoke_user_access(payload.user_id)
    return {"status": "ok", "user_id": payload.user_id, "has_access": payload.grant}

class AdminBroadcastRequest(BaseModel):
    text: str
    target: str = "all"  # 'all', 'paid', 'free'

@app.post("/api/admin/broadcast")
async def api_admin_broadcast(payload: AdminBroadcastRequest):
    user_ids = await get_broadcast_user_ids(payload.target)
    sent_count = 0
    try:
        from bot_instance import bot
        for uid in user_ids:
            try:
                await bot.send_message(chat_id=uid, text=payload.text, parse_mode="HTML")
                sent_count += 1
            except Exception:
                pass
    except Exception as e:
        print(f"Broadcast error: {e}")
    return {"status": "ok", "target": payload.target, "total": len(user_ids), "sent": sent_count}

# API Endpoints для Mini App

@app.get("/api/user/data")
async def get_user_data(user_id: int = 123456789, init_data: Optional[str] = None):
    verified_id = get_verified_user_id(init_data, user_id)
    progress = await get_user_progress(verified_id)
    measurements = await get_user_measurements(verified_id)
    has_access = await check_user_access(verified_id)
    profile = await get_user_profile(verified_id)

    return {
        "user_id": verified_id,
        "has_access": has_access,
        "completed_days": progress,
        "measurements": measurements,
        "profile": profile
    }

@app.post("/api/user/profile")
async def save_profile_endpoint(payload: ProfileRequest):
    verified_id = get_verified_user_id(payload.init_data, payload.user_id)
    await save_user_profile(
        user_id=verified_id,
        gender=payload.gender,
        age=payload.age,
        height=payload.height,
        current_weight=payload.current_weight,
        target_weight=payload.target_weight,
        waist=payload.waist,
        hips=payload.hips,
        goal=payload.goal,
        activity_level=payload.activity_level,
        daily_calories_target=payload.daily_calories_target
    )
    # Также сохраняем замер в дневник замеров
    await save_user_measurement(verified_id, payload.current_weight, payload.waist, payload.hips)
    fire_and_forget(sync_user_to_gas(
        user_id=verified_id,
        goal=payload.goal,
        height=payload.height,
        current_weight=payload.current_weight,
        target_weight=payload.target_weight,
        waist=payload.waist,
        hips=payload.hips
    ))
    profile = await get_user_profile(verified_id)
    measurements = await get_user_measurements(verified_id)
    return {"status": "ok", "profile": profile, "measurements": measurements}

@app.post("/api/progress/toggle")
async def toggle_progress(payload: ProgressToggleRequest):
    verified_id = get_verified_user_id(payload.init_data, payload.user_id)
    await save_user_progress(verified_id, payload.day, payload.completed)
    if payload.completed:
        fire_and_forget(log_workout_to_gas(verified_id, payload.day))
    return {"status": "ok", "day": payload.day, "completed": payload.completed}

@app.post("/api/measurements/add")
async def add_measurement(payload: MeasurementRequest):
    verified_id = get_verified_user_id(payload.init_data, payload.user_id)
    await save_user_measurement(verified_id, payload.weight, payload.waist, payload.hips)
    measurements = await get_user_measurements(verified_id)
    return {"status": "ok", "measurements": measurements}

@app.post("/api/ai/ask")
async def ai_chat_endpoint(payload: AIChatRequest):
    verified_id = get_verified_user_id(payload.init_data, payload.user_id)
    await add_ai_message(verified_id, "user", payload.question)
    history = await get_recent_ai_history(verified_id, limit=6)
    reply = await ask_ai_coach(payload.question, history)
    await add_ai_message(verified_id, "model", reply)
    return {"status": "ok", "reply": reply}

@app.post("/api/nutrition/analyze-photo")
async def analyze_photo_endpoint(
    file: UploadFile = File(...),
    user_id: int = Form(123456789),
    init_data: Optional[str] = Form(None)
):
    """
    Принимает фото тарелки с едой, распознает блюдо и вычисляет КБЖУ через Gemini Vision.
    Возвращает структуру для подтверждения/редактирования пользователем.
    """
    try:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"
        analysis = await analyze_food_photo(image_bytes, mime_type)
        return {"status": "ok", "analysis": analysis}
    except Exception as e:
        logger.exception(f"Error in analyze_photo_endpoint: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Ошибка анализа фото: {str(e)}"}
        )

@app.post("/api/nutrition/analyze-audio")
async def analyze_audio_endpoint(
    file: UploadFile = File(...),
    user_id: int = Form(123456789),
    init_data: Optional[str] = Form(None)
):
    """
    Принимает аудиозапись с описанием еды, распознает речь и рассчитывает КБЖУ.
    Возвращает структуру для подтверждения/редактирования пользователем.
    """
    try:
        audio_bytes = await file.read()
        mime_type = file.content_type or "audio/ogg"
        analysis = await analyze_food_audio(audio_bytes, mime_type)
        return {"status": "ok", "analysis": analysis}
    except Exception as e:
        logger.exception(f"Error in analyze_audio_endpoint: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Ошибка анализа аудио: {str(e)}"}
        )

@app.post("/api/nutrition/save-meal")
async def save_meal_endpoint(payload: SaveMealRequest):
    """
    Сохраняет проверенный/отредактированный пользователем приём пищи в базу и Google Таблицу.
    """
    verified_id = get_verified_user_id(payload.init_data, payload.user_id)
    
    meal_id = await save_user_meal(
        user_id=verified_id,
        dish_name=payload.dish_name,
        calories=payload.calories,
        protein=payload.protein,
        fats=payload.fats,
        carbs=payload.carbs,
        advice=payload.advice or "",
        omega3_score=payload.omega3_score or 25,
        aojiru_score=payload.aojiru_score or 30,
        vitamins_score=payload.vitamins_score or 50
    )

    # await вместо fire_and_forget: на serverless фоновая задача обрывается после ответа
    await log_meal_to_gas(
        user_id=verified_id,
        dish_name=payload.dish_name,
        input_type=payload.input_type or "Фото",
        calories=payload.calories,
        protein=payload.protein,
        fats=payload.fats,
        carbs=payload.carbs,
        health_score=9.0,
        advice=payload.advice or ""
    )

    return {"status": "ok", "meal_id": meal_id}

@app.post("/api/nutrition/delete-meal")
async def delete_meal_endpoint(payload: DeleteMealRequest):
    """
    Удаляет приём пищи из базы.
    """
    verified_id = get_verified_user_id(payload.init_data, payload.user_id)
    if payload.meal_id:
        import aiosqlite
        async with aiosqlite.connect(settings.DB_PATH) as db:
            await db.execute("DELETE FROM user_meals WHERE id = ? AND user_id = ?", (payload.meal_id, verified_id))
            await db.commit()
    elif payload.dish_name:
        import aiosqlite
        async with aiosqlite.connect(settings.DB_PATH) as db:
            await db.execute(
                "DELETE FROM user_meals WHERE id = (SELECT MAX(id) FROM user_meals WHERE user_id = ? AND dish_name = ? AND calories = ?)",
                (verified_id, payload.dish_name, payload.calories or 0))
            await db.commit()
    if payload.dish_name:
        await delete_meal_in_gas(verified_id, payload.dish_name, payload.calories or 0)
    return {"status": "ok"}

@app.get("/api/nutrition/meals")
async def get_meals_endpoint(user_id: int = 123456789, init_data: Optional[str] = None):
    verified_id = get_verified_user_id(init_data, user_id)
    meals = await get_user_meals(verified_id)

    # Google Таблица — источник истины (SQLite на Vercel временный)
    gas_meals = await fetch_meals_from_gas(verified_id)
    if gas_meals:
        gas_keys = {(str(g.get("dish_name")), int(float(g.get("calories") or 0))) for g in gas_meals}
        merged = [
            {
                "dish_name": g.get("dish_name"),
                "calories": int(float(g.get("calories") or 0)),
                "protein": float(g.get("protein") or 0),
                "fats": float(g.get("fats") or 0),
                "carbs": float(g.get("carbs") or 0),
                "advice": g.get("advice") or "",
                "created_at": str(g.get("created_at") or ""),
            }
            for g in reversed(gas_meals)
        ]
        merged += [m for m in meals if (str(m.get("dish_name")), int(m.get("calories") or 0)) not in gas_keys]
        meals = merged

    total_cal = sum(m.get("calories", 0) for m in meals)
    total_p = sum(m.get("protein", 0) for m in meals)
    total_f = sum(m.get("fats", 0) for m in meals)
    total_c = sum(m.get("carbs", 0) for m in meals)

    count = len(meals) or 1
    avg_omega3 = int(sum(m.get("omega3_score", 25) for m in meals) / count)
    avg_aojiru = int(sum(m.get("aojiru_score", 30) for m in meals) / count)
    avg_vitamins = int(sum(m.get("vitamins_score", 50) for m in meals) / count)

    latest_rec = None
    if meals and meals[0].get("recommendation_json"):
        try:
            import json
            latest_rec = json.loads(meals[0]["recommendation_json"])
        except Exception:
            pass

    return {
        "status": "ok",
        "meals": meals,
        "summary": {
            "total_calories": total_cal,
            "total_protein": round(total_p, 1),
            "total_fats": round(total_f, 1),
            "total_carbs": round(total_c, 1),
            "omega3_score": avg_omega3,
            "aojiru_score": avg_aojiru,
            "vitamins_score": avg_vitamins,
            "recommendation": latest_rec
        }
    }

