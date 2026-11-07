import aiohttp
import base64
import json
import logging
from typing import List, Dict, Any
from config import settings

logger = logging.getLogger(__name__)

JANAFIT_COACH_SYSTEM_PROMPT = """Ты — персональный AI-тренер и нутрициолог онлайн-проекта Janafit.
Твоя цель: поддерживать участниц курса, помогать им безопасно тренироваться, отвечать на вопросы по упражнениям, питанию, технике и восстановлению.

Правила общения:
1. Тон: дружелюбный, поддерживающий, вдохновляющий и тактичный (обращайся тепло и с заботой).
2. Безопасность превыше всего: если у пользователя болят колени, спина или шея — всегда давай безопасную альтернативу (например, замена прыжков на шаги, замена глубоких приседаний на ягодичный мостик).
3. Питание: пропагандируй адекватный баланс (белки, полезные жиры, сложные углеводы, 1.5-2л воды в день), никаких жестких голодовок.
4. Знание программы: курс Janafit длится 21 день, уроки по 25-35 минут, без сложного инвентаря (достаточно коврика и бутылочек/резинок).
5. Если вопрос касается серьезных травм, болезней или острой боли — мягко порекомендуй проконсультироваться с врачом и нажать кнопку «Связаться с куратором».
6. Отвечай кратко, емко и по делу, форматируя текст с эмодзи и списками для удобного чтения с телефона.
"""

async def ask_ai_coach(user_message: str, history: List[Dict[str, str]] = None) -> str:
    """
    Отправляет запрос в Google Gemini API.
    В случае отсутствия ключа или ошибки возвращает качественный заготовленный ответ.
    """
    if not settings.GEMINI_API_KEY:
        return (
            "💪 Привет! Я твой AI-тренер Janafit.\n\n"
            "Я всегда на связи, чтобы помочь с тренировками и питанием:\n"
            "• Подскажу замену упражнения при дискомфорте в суставах\n"
            "• Помогу составить меню до и после тренировки\n"
            "• Поддержу, если пропала мотивация!\n\n"
            "<i>(Для включения живого ИИ-диалога укажите GEMINI_API_KEY в настройках .env)</i>\n\n"
            f"Твой вопрос был: «{user_message}»\n\n"
            "Если нужна срочная помощь живого куратора, нажми кнопку <b>«💬 Написать тренеру»</b>."
        )

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={settings.GEMINI_API_KEY}"
        
        contents = []
        contents.append({
            "role": "user",
            "parts": [{"text": f"Инструкция: {JANAFIT_COACH_SYSTEM_PROMPT}"}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "Поняла! Я персональный AI-тренер Janafit. Готова помогать ученицам."}]
        })

        if history:
            for item in history[-6:]:
                role = "user" if item["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": item["content"]}]
                })

        contents.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 800
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        return text
                else:
                    err_text = await resp.text()
                    logger.error(f"Gemini API error {resp.status}: {err_text}")
    except Exception as e:
        logger.exception(f"Error calling AI coach: {e}")

    return (
        "Тренировка — это забота о себе! 🧘‍♀️\n"
        "Главное правило Janafit: при любом дискомфорте снижай амплитуду и темп. "
        "Слушай свое тело, пей воду маленькими глотками.\n\n"
        "Если вопрос требует личного разбора — напиши нашему дежурному тренеру!"
    )

async def analyze_food_photo(image_bytes: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """
    Анализирует фотографию еды через Gemini Vision.
    Определяет состав, калорийность, белки, жиры, углеводы и выдает персональный совет тренера Janafit.
    """
    b64_image = base64.b64encode(image_bytes).decode('utf-8')

    prompt = (
        "Ты — профессиональный AI-нутрициолог курса похудения Janafit. "
        "Внимательно изучи это фото еды на тарелке.\n"
        "Определи ингредиенты, примерный вес порции в граммах, калорийность (ккал) и КБЖУ (белки, жиры, углеводы в граммах).\n"
        "Дай оценку пользы по шкале от 1 до 10 и практичный совет для участницы курса.\n\n"
        "Ответь СТРОГО в формате валидного JSON (без лишнего текста вокруг, без кавычек markdown):\n"
        "{\n"
        '  "dish_name": "Название блюда",\n'
        '  "weight_g": 350,\n'
        '  "calories": 420,\n'
        '  "protein": 28,\n'
        '  "fats": 12,\n'
        '  "carbs": 44,\n'
        '  "ingredients": ["Ингредиент 1 ~150г", "Ингредиент 2 ~100г"],\n'
        '  "health_score": 9,\n'
        '  "verdict": "Идеально сбалансированный прием пищи для похудения!",\n'
        '  "advice": "Отличный баланс чистого белка и клетчатки. Поможет держать сытость без срывов."\n'
        "}"
    )

    if not settings.GEMINI_API_KEY:
        # Реалистичный демо-ответ, если ключ API пока не указан
        return {
            "dish_name": "Боул с индейкой, киноа и свежими овощами",
            "weight_g": 340,
            "calories": 385,
            "protein": 31,
            "fats": 11,
            "carbs": 42,
            "ingredients": ["Филе индейки на пару ~130г", "Киноа отварное ~110г", "Огурцы, черри и шпинат ~100г"],
            "health_score": 9.5,
            "verdict": "Эталонная тарелка Janafit! Идеально для жиросжигания.",
            "advice": "Великолепный баланс! Много чистого белка для тонуса мышц и медленные углеводы для стабильной энергии без скачков сахара."
        }

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=25) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_json = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        # Очищаем от возможных оберток
                        cleaned = raw_json.strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        return json.loads(cleaned.strip())
                else:
                    err = await resp.text()
                    logger.error(f"Gemini Vision error {resp.status}: {err}")
    except Exception as e:
        logger.exception(f"Error analyzing food photo: {e}")

    # Запасной фоллбэк
    return {
        "dish_name": "Сбалансированное блюдо",
        "weight_g": 320,
        "calories": 410,
        "protein": 26,
        "fats": 14,
        "carbs": 45,
        "ingredients": ["Белковая основа", "Сложный гарнир", "Овощной салат"],
        "health_score": 8.5,
        "verdict": "Хороший питательный прием пищи.",
        "advice": "Старайтесь, чтобы половину тарелки всегда занимала свежая зелень и овощи."
    }

