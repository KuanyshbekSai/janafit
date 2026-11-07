from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import io

from config import settings
from database import add_ai_message, get_recent_ai_history, save_user_meal
from services.ai_service import ask_ai_coach, analyze_food_photo, analyze_food_audio
from services.gas_sync import fire_and_forget, log_meal_to_gas

router = Router()

class AICoachStates(StatesGroup):
    chatting = State()
    waiting_live_question = State()

@router.callback_query(F.data == "ai_coach_start")
async def cb_ai_coach_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AICoachStates.chatting)

    text = (
        "🤖 <b>AI-тренер Janafit на связи!</b> 🌸\n\n"
        "Я знаю всё о программе тренировок Janafit, питании и технике выполнения.\n\n"
        "<b>С чем я могу помочь:</b>\n"
        "• <i>«Болит колено во время выпадов, чем заменить?»</i>\n"
        "• <i>«Что лучше съесть за час до тренировки?»</i>\n"
        "• <i>«Не успеваю 30 минут, как сократить занятие без потери эффекта?»</i>\n"
        "• <i>«Тянет на сладкое вечером, что делать?»</i>\n\n"
        "✍️ <b>Напишите ваш вопрос прямо в чат сообщением:</b>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Позвать живого тренера", callback_data="call_live_coach")],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_start")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(AICoachStates.chatting, F.text)
async def process_ai_coach_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_query = message.text

    # Сохраняем вопрос
    await add_ai_message(user_id, "user", user_query)

    # Показываем статус набора
    await message.bot.send_chat_action(message.chat.id, "typing")

    history = await get_recent_ai_history(user_id, limit=6)
    ai_reply = await ask_ai_coach(user_query, history)

    # Сохраняем ответ
    await add_ai_message(user_id, "model", ai_reply)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать живому куратору", callback_data="call_live_coach")],
        [InlineKeyboardButton(text="◀️ Завершить диалог", callback_data="back_to_start")]
    ])

    await message.answer(ai_reply, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "call_live_coach")
async def cb_call_live_coach(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AICoachStates.waiting_live_question)

    text = (
        "👩‍🏫 <b>Связь с дежурным тренером Janafit</b>\n\n"
        "Наши тренеры готовы разобрать твою технику, скорректировать нагрузку или помочь с личными нюансами.\n\n"
        "✍️ <b>Опиши свой вопрос или прикрепи короткое видео с техникой упражнения одним сообщением:</b>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="back_to_start")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(AICoachStates.waiting_live_question)
async def process_live_coach_question(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    await state.clear()

    await message.answer(
        "✅ <b>Ваш вопрос передан дежурному тренеру!</b>\n"
        "Мы ответим вам прямо в этом чате в ближайшее время.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_start")]
        ]),
        parse_mode="HTML"
    )

    # Отправляем вопрос в админ / тренерский чат
    targets = [settings.SUPPORT_CHAT_ID] if settings.SUPPORT_CHAT_ID else settings.admin_id_list
    admin_caption = (
        f"🆘 <b>Вопрос дежурному тренеру!</b>\n\n"
        f"От: @{message.from_user.username or 'без_юзернейма'} (ID: <code>{user_id}</code>, {message.from_user.full_name})\n"
        f"Сообщение: {message.text or '[Медиафайл]'}"
    )

@router.message(F.photo)
async def process_food_photo(message: Message, bot: Bot, state: FSMContext):
    # Если пользователь в процессе ожидания чека Kaspi — пусть хэндлер checkout обработает его
    current_state = await state.get_state()
    if current_state and "waiting_for_receipt" in current_state:
        return

    wait_msg = await message.answer("🔍 <b>Анализирую фото тарелки через AI...</b>\nСчитаю калории и баланс КБЖУ 🥗", parse_mode="HTML")
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()

        analysis = await analyze_food_photo(image_bytes)

        dish = analysis.get("dish_name", "Блюдо")
        weight = analysis.get("weight_g", 300)
        cal = analysis.get("calories", 400)
        p = analysis.get("protein", 25)
        f = analysis.get("fats", 12)
        c = analysis.get("carbs", 40)
        score = analysis.get("health_score", 8.5)
        verdict = analysis.get("verdict", "Сбалансированное блюдо")
        advice = analysis.get("advice", "")
        omega3 = analysis.get("omega3_score", 25)
        aojiru = analysis.get("aojiru_greens_score", 30)
        vitamins = analysis.get("vitamins_score", 50)
        rec = analysis.get("recommendation", {})

        import json
        rec_json = json.dumps(rec, ensure_ascii=False) if rec else None

        # Сохраняем в дневник
        await save_user_meal(
            user_id=message.from_user.id,
            dish_name=dish,
            calories=cal,
            protein=p,
            fats=f,
            carbs=c,
            advice=advice,
            omega3_score=omega3,
            aojiru_score=aojiru,
            vitamins_score=vitamins,
            recommendation_json=rec_json
        )

        fire_and_forget(log_meal_to_gas(
            user_id=message.from_user.id,
            dish_name=dish,
            input_type="Фото",
            calories=cal,
            protein=p,
            fats=f,
            carbs=c,
            health_score=score,
            advice=advice
        ))

        reply_text = (
            f"🍽 <b>{dish}</b> (~{weight} г)\n\n"
            f"🔥 <b>Калорийность:</b> {cal} ккал\n"
            f"🍗 Белки: <b>{p} г</b> | 🥑 Жиры: <b>{f} г</b> | 🍚 Углеводы: <b>{c} г</b>\n\n"
            f"💊 <b>Баланс микронутриентов:</b>\n"
            f"• Омега-3 (ПНЖК): <b>{omega3}%</b> нормы\n"
            f"• Зеленые энзимы и клетчатка: <b>{aojiru}%</b> нормы\n"
            f"• Витаминный индекс (D3, B, Mg, Zn): <b>{vitamins}%</b>\n\n"
            f"💡 <b>Совет нутрициолога:</b>\n{advice}\n"
        )

        buttons = [
            [InlineKeyboardButton(text="📱 Открыть дневник в Mini App", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
            [InlineKeyboardButton(text="💬 Спросить тренера", callback_data="ai_coach_start")]
        ]

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await wait_msg.delete()
        await message.answer(reply_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await wait_msg.edit_text("Не удалось проанализировать фото. Попробуйте сделать снимок ближе при хорошем освещении.")

@router.message(F.voice)
async def handle_voice_meal(message: Message, bot: Bot):
    """
    Принимает голосовое сообщение, когда пользователь забыл сфотографировать еду.
    Распознает блюдо, вычисляет КБЖУ, сохраняет в дневник питания и дает советы.
    """
    wait_msg = await message.answer("🎙 <i>Слушаю вашу голосовую запись о еде, считаю калории и БЖУ...</i>", parse_mode="HTML")

    try:
        voice = message.voice
        file_io = io.BytesIO()
        await bot.download(voice, destination=file_io)
        audio_bytes = file_io.getvalue()

        analysis = await analyze_food_audio(audio_bytes, mime_type="audio/ogg")

        dish = analysis.get("dish_name", "Голосовая запись")
        weight = analysis.get("weight_g", 300)
        cal = analysis.get("calories", 400)
        p = analysis.get("protein", 25)
        f = analysis.get("fats", 12)
        c = analysis.get("carbs", 40)
        advice = analysis.get("advice", "")
        omega3 = analysis.get("omega3_score", 25)
        aojiru = analysis.get("aojiru_greens_score", 30)
        vitamins = analysis.get("vitamins_score", 50)

        # Сохраняем в дневник
        await save_user_meal(
            user_id=message.from_user.id,
            dish_name=dish,
            calories=cal,
            protein=p,
            fats=f,
            carbs=c,
            advice=advice,
            omega3_score=omega3,
            aojiru_score=aojiru,
            vitamins_score=vitamins
        )

        fire_and_forget(log_meal_to_gas(
            user_id=message.from_user.id,
            dish_name=dish,
            input_type="Голос",
            calories=cal,
            protein=p,
            fats=f,
            carbs=c,
            health_score=8.8,
            advice=advice
        ))

        reply_text = (
            f"🎙 <b>Голосовая запись учтена в дневнике!</b>\n\n"
            f"🍽 <b>{dish}</b> (~{weight} г)\n\n"
            f"🔥 <b>Калорийность:</b> {cal} ккал\n"
            f"🍗 Белки: <b>{p} г</b> | 🥑 Жиры: <b>{f} г</b> | 🍚 Углеводы: <b>{c} г</b>\n\n"
            f"💊 <b>Баланс микронутриентов:</b>\n"
            f"• Омега-3: <b>{omega3}%</b> нормы\n"
            f"• Свежая зелень и клетчатка: <b>{aojiru}%</b>\n"
            f"• Витамины и минералы: <b>{vitamins}%</b>\n\n"
            f"💡 <b>Совет нутрициолога:</b>\n{advice}\n"
        )

        buttons = [
            [InlineKeyboardButton(text="📱 Открыть дневник в Mini App", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
            [InlineKeyboardButton(text="💬 Спросить тренера", callback_data="ai_coach_start")]
        ]

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await wait_msg.delete()
        await message.answer(reply_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await wait_msg.edit_text("Не удалось распознать голосовое сообщение. Попробуйте надиктовать еще раз четче или ввести текстом.")


