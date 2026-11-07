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
        "Ты — профессиональный AI-нутрициолог курса Janafit и эксперт по микронутриентам.\n"
        "Внимательно изучи это фото еды на тарелке.\n"
        "1. Определи блюдо, примерный вес в граммах, калорийность (ккал) и КБЖУ (белки, жиры, углеводы в граммах).\n"
        "2. Рассчитай микронутриентный баланс блюда в % от разовой нормы:\n"
        "   - omega3_score (0-100): наличие Омега-3 (жирная рыба, семена чиа/льна). Если их нет — 10-25%.\n"
        "   - aojiru_greens_score (0-100): наличие зелени, хлорофилла, энзимов для ЖКТ и детокса (ячмень, шпинат, зелень). Если мало зелени — 15-30%.\n"
        "   - vitamins_score (0-100): общий витаминный индекс (B-группа, D3, магний, цинк, антиоксиданты).\n"
        "3. Выяви главный микронутриентный дефицит в этой тарелке и сформируй нативную рекомендацию одного из фирменных продуктов линейки Janafit:\n"
        "   - 'omega3' (Омега-3): если в блюде дефицит полезных жиров для кожи, сосудов и жиросжигания.\n"
        "   - 'aojiru' (Японский Аодзиру): если мало сырой зелени, клетчатки и ферментов для легкого пищеварения.\n"
        "   - 'women_vitamins' (Женский витаминный комплекс): если не хватает комплекса витаминов для энергии и тонуса.\n"
        "   - 'men_vitamins' (Мужской витаминный комплекс): если тарелка мужская/сытная, но не хватает цинка/магния.\n\n"
        "Ответь СТРОГО в формате валидного JSON (без кавычек markdown):\n"
        "{\n"
        '  "dish_name": "Название блюда",\n'
        '  "weight_g": 350,\n'
        '  "calories": 420,\n'
        '  "protein": 28,\n'
        '  "fats": 12,\n'
        '  "carbs": 44,\n'
        '  "ingredients": ["Ингредиент 1 ~150г", "Ингредиент 2 ~100г"],\n'
        '  "health_score": 9.0,\n'
        '  "omega3_score": 25,\n'
        '  "aojiru_greens_score": 30,\n'
        '  "vitamins_score": 55,\n'
        '  "verdict": "Хороший сытный прием пищи, но наблюдается нехватка омега-кислот и зеленых ферментов.",\n'
        '  "advice": "Отличный баланс белка. Для максимального эффекта дополните рацион правильными микронутриентами.",\n'
        '  "recommendation": {\n'
        '    "product_id": "omega3",\n'
        '    "product_name": "Janafit Omega-3 Ultra Pure (Iceland)",\n'
        '    "short_reason": "В тарелке дефицит Омега-3 (25%). Восполните омега-кислоты для упругости кожи и ускорения липолиза.",\n'
        '    "discount_price": "6 990 ₸ (вместо 8 900 ₸)",\n'
        '    "action_url": "https://t.me/janafit_bot?start=vit_omega3"\n'
        '  }\n'
        "}"
    )

    if not settings.GEMINI_API_KEY:
        return {
            "dish_name": "Боул с индейкой, киноа и свежими овощами",
            "weight_g": 340,
            "calories": 385,
            "protein": 31,
            "fats": 11,
            "carbs": 42,
            "ingredients": ["Филе индейки на пару ~130г", "Киноа отварное ~110г", "Огурцы, черри и шпинат ~100г"],
            "health_score": 9.5,
            "omega3_score": 20,
            "aojiru_greens_score": 40,
            "vitamins_score": 65,
            "verdict": "Эталонная тарелка Janafit! Идеально для жиросжигания.",
            "advice": "Великолепный баланс! Много чистого белка для тонуса мышц и медленные углеводы для стабильной энергии.",
            "recommendation": {
                "product_id": "omega3",
                "product_name": "Janafit Omega-3 Ultra Pure",
                "short_reason": "В этой порции всего 20% Омега-3. Добавьте 2 капсулы после еды для защиты связок и сияния кожи.",
                "discount_price": "6 990 ₸ (скидка 22%)",
                "action_url": "https://t.me/janafit_bot?start=vit_omega3"
            }
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

