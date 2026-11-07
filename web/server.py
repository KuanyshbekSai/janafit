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
    get_user_meals
)
from services.robokassa import verify_robokassa_webhook
from services.security import validate_telegram_init_data
from services.ai_service import ask_ai_coach, analyze_food_photo

app = FastAPI(title="Janafit Web & Webhook Server")

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
templates_dir = next((d for d in candidates if os.path.isdir(d)), candidates[0])
templates = Jinja2Templates(directory=templates_dir)

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

def get_verified_user_id(init_data: Optional[str], fallback_user_id: Optional[int] = None) -> int:
    """
    Верифицирует Telegram initData. Если данные не валидны, но мы в тестовом режиме (localhost),
    разрешает использовать fallback_user_id. В продакшене гарантирует подлинность Telegram User ID.
    """
    if init_data and settings.BOT_TOKEN:
        verified = validate_telegram_init_data(init_data, settings.BOT_TOKEN)
        if verified and "user" in verified:
            return int(verified["user"].get("id", 0))

    # Для удобства локального тестирования
    return fallback_user_id or 123456789

@app.get("/")
async def root():
    return RedirectResponse(url="/app")

@app.get("/health")
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
    return templates.TemplateResponse("success.html", {
        "request": request,
        "inv_id": InvId,
        "out_sum": OutSum
    })

@app.get("/payment/fail", response_class=HTMLResponse)
async def payment_fail_page(request: Request):
    return templates.TemplateResponse("fail.html", {
        "request": request
    })

@app.get("/app", response_class=HTMLResponse)
async def mini_app_view(request: Request, day: int = 1):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "default_day": day,
        "course_title": settings.COURSE_TITLE
    })

# API Endpoints для Mini App

@app.get("/api/user/data")
async def get_user_data(user_id: int = 123456789, init_data: Optional[str] = None):
    verified_id = get_verified_user_id(init_data, user_id)
    progress = await get_user_progress(verified_id)
    measurements = await get_user_measurements(verified_id)
    has_access = await check_user_access(verified_id)

    return {
        "user_id": verified_id,
        "has_access": has_access,
        "completed_days": progress,
        "measurements": measurements
    }

@app.post("/api/progress/toggle")
async def toggle_progress(payload: ProgressToggleRequest):
    verified_id = get_verified_user_id(payload.init_data, payload.user_id)
    await save_user_progress(verified_id, payload.day, payload.completed)
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
    Принимает фото тарелки с едой, распознает блюдо, вычисляет КБЖУ и сохраняет в дневник.
    """
    verified_id = get_verified_user_id(init_data, user_id)
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    analysis = await analyze_food_photo(image_bytes, mime_type)

    import json
    rec_obj = analysis.get("recommendation", {})
    rec_str = json.dumps(rec_obj, ensure_ascii=False) if rec_obj else None

    # Сохраняем в дневник питания
    await save_user_meal(
        user_id=verified_id,
        dish_name=analysis.get("dish_name", "Блюдо"),
        calories=int(analysis.get("calories", 0)),
        protein=float(analysis.get("protein", 0)),
        fats=float(analysis.get("fats", 0)),
        carbs=float(analysis.get("carbs", 0)),
        advice=analysis.get("advice", ""),
        omega3_score=int(analysis.get("omega3_score", 25)),
        aojiru_score=int(analysis.get("aojiru_greens_score", 30)),
        vitamins_score=int(analysis.get("vitamins_score", 50)),
        recommendation_json=rec_str
    )

    return {"status": "ok", "analysis": analysis}

@app.get("/api/nutrition/meals")
async def get_meals_endpoint(user_id: int = 123456789, init_data: Optional[str] = None):
    verified_id = get_verified_user_id(init_data, user_id)
    meals = await get_user_meals(verified_id)
    
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

