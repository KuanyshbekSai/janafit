from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_or_create_user, check_user_access
from config import settings
from services.gas_sync import fire_and_forget, sync_user_to_gas

router = Router()

def get_main_menu(has_access: bool) -> InlineKeyboardMarkup:
    if has_access:
        buttons = [
            [InlineKeyboardButton(text="▶️ Перейти к тренировкам", callback_data="open_course")],
            [InlineKeyboardButton(text="📱 Открыть Web-приложение (Mini App)", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
            [InlineKeyboardButton(text="🤖 Чат с AI-тренером 24/7", callback_data="ai_coach_start")],
            [InlineKeyboardButton(text="💬 Написать живому куратору", callback_data="call_live_coach")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text=f"🔥 Забрать курс за {settings.COURSE_PRICE:,} ₸ (990 ₽)", callback_data="buy_course")],
            [InlineKeyboardButton(text="🎬 Тестовый просмотр уроков (Демо)", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
            [InlineKeyboardButton(text="📋 Что внутри курса (Программа)", callback_data="about_course")],
            [InlineKeyboardButton(text="⭐️ Результаты участниц До/После", callback_data="testimonials")],
            [InlineKeyboardButton(text="🤖 Задать вопрос AI-тренеру", callback_data="ai_coach_start")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    user = await get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    has_access = bool(user.get("has_access"))

    fire_and_forget(sync_user_to_gas(
        user_id=message.from_user.id,
        name=f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(),
        username=message.from_user.username or "",
        has_access=has_access
    ))

    if has_access:
        text = (
            f"👋 С возвращением, <b>{message.from_user.first_name}</b>!\n\n"
            f"Твой доступ к курсу <b>«{settings.COURSE_TITLE}»</b> активен.\n"
            f"Готова к сегодняшней тренировке? Выбирай действие ниже:"
        )
    else:
        text = (
            f"✨ <b>Добро пожаловать в Janafit!</b> ✨\n\n"
            f"Твоя трансформация начинается здесь. Готовая авторская программа тренировок для дома и зала, "
            f"которая подтягивает тело, убирает объемы и возвращает легкость.\n\n"
            f"⚡️ <b>СПЕЦИАЛЬНОЕ ПРЕДЛОЖЕНИЕ:</b>\n"
            f"Стоимость сегодня: <b>{settings.COURSE_PRICE:,} ₸</b> <s>{settings.COURSE_ORIGINAL_PRICE:,} ₸</s> (-44%)\n\n"
            f"🎯 <b>Что ты получишь сразу после оплаты:</b>\n"
            f"• 21 видеоурок высокой четкости с таймерами и разбором техники\n"
            f"• Программа питания без строгих диет и голода\n"
            f"• Доступ в закрытый закрытый VIP-клуб Janafit\n"
            f"• Круглосуточный AI-тренер и поддержка живых кураторов"
        )

    await message.answer(text, reply_markup=get_main_menu(has_access), parse_mode="HTML")

@router.callback_query(F.data == "about_course")
async def cb_about_course(callback: CallbackQuery):
    text = (
        f"📋 <b>ПРОГРАММА КУРСА JANAFIT (21 ДЕНЬ)</b>\n\n"
        f"<b>Неделя 1: Мягкий старт и лимфодренаж</b>\n"
        f"• День 1: Пробуждение мышц + дыхательные практики\n"
        f"• День 2: Осанка, спина и раскрытие грудного отдела\n"
        f"• День 3: Упругие ягодицы без нагрузки на колени\n\n"
        f"<b>Неделя 2: Сжигание объемов и рельеф</b>\n"
        f"• День 4: Плоский живот и глубокие мышцы кора\n"
        f"• День 5: Стройные ноги и внутренняя поверхность бедра\n"
        f"• День 6: Кардио-тонус для ускорения метаболизма\n\n"
        f"<b>Неделя 3: Фиксация результата и гибкость</b>\n"
        f"• Комплексы Full Body + легкая растяжка\n\n"
        f"⏱ <i>Длительность уроков: всего 20-30 минут в день. Без громоздких тренажеров!</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Купить за {settings.COURSE_PRICE:,} ₸", callback_data="buy_course")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "testimonials")
async def cb_testimonials(callback: CallbackQuery):
    text = (
        f"⭐️ <b>РЕЗУЛЬТАТЫ УЧАСТНИЦ JANAFIT</b>\n\n"
        f"💬 <i>«Минус 4.2 кг за 3 недели без срывов! Самое приятное — ушла отечность по утрам и перестала болеть поясница.»</i> — Алия, 29 лет\n\n"
        f"💬 <i>«Очень понятные уроки, таймер прямо перед глазами. Занималась дома, пока ребенок спал. Муж сделал кучу комплиментов!»</i> — Динара, 34 года\n\n"
        f"💬 <i>«Курс просто пушка за 4 990 ₸. Никакой воды, всё по делу!»</i> — Мадина, 26 лет"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔥 Начать сейчас за {settings.COURSE_PRICE:,} ₸", callback_data="buy_course")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_to_start")
async def cb_back_to_start(callback: CallbackQuery):
    has_access = await check_user_access(callback.from_user.id)
    text = (
        f"✨ <b>Janafit — твой путь к телу мечты</b>\n\n"
        f"Оффер: доступ ко всем материалам всего за <b>{settings.COURSE_PRICE:,} ₸</b> вместо <s>{settings.COURSE_ORIGINAL_PRICE:,} ₸</s>."
    )
    await callback.message.edit_text(text, reply_markup=get_main_menu(has_access), parse_mode="HTML")
    await callback.answer()
