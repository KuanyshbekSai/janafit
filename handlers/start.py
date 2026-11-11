from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)
from database import get_or_create_user, check_user_access
from config import settings
from services.gas_sync import fire_and_forget, sync_user_to_gas

router = Router()

def get_persistent_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌸 Открыть Janafit (Mini App)", web_app=WebAppInfo(url=f"{settings.BASE_WEB_URL}/app"))],
            [KeyboardButton(text="🤖 AI-Тренер 24/7"), KeyboardButton(text="📚 Мои тренировки")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )

def get_main_menu(has_access: bool) -> InlineKeyboardMarkup:
    if has_access:
        buttons = [
            [InlineKeyboardButton(text="📱 Открыть Mini App (Плеер + Дневник)", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
            [InlineKeyboardButton(text="▶️ Список уроков в чате", callback_data="open_course")],
            [InlineKeyboardButton(text="🤖 Чат с AI-тренером 24/7", callback_data="ai_coach_start")],
            [InlineKeyboardButton(text="💬 Написать живому куратору", callback_data="call_live_coach")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="🎁 2 Бесплатные тренировки (Тест-драйв)", callback_data="free_workouts")],
            [InlineKeyboardButton(text="🎬 Советы Айтыма Жакупова (Reels)", callback_data="aitym_reels")],
            [InlineKeyboardButton(text=f"🔥 Участвовать в марафоне за {settings.COURSE_PRICE:,} ₸", callback_data="buy_course")],
            [InlineKeyboardButton(text="📱 Открыть Janafit App", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
            [InlineKeyboardButton(text="📋 Программа (14 уроков + Психолог + Врачи)", callback_data="about_course")],
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
            f"✨ <b>Добро пожаловать в Janafit!</b> ✨\n"
            f"<i>Авторский 14-дневный марафон трансформации от Айтыма Жакупова</i>\n\n"
            f"🎁 <b>Вам доступны 2 полноценные бесплатные тренировки!</b>\n"
            f"Оцените качество видео, подачу и почувствуйте включение мышц прямо сейчас.\n\n"
            f"⚡️ <b>ПОЛНЫЙ ДОСТУП К МАРАФОНУ:</b>\n"
            f"Стоимость сегодня: <b>{settings.COURSE_PRICE:,} ₸</b> <s>{settings.COURSE_ORIGINAL_PRICE:,} ₸</s>\n\n"
            f"🎯 <b>Что входит в программу:</b>\n"
            f"• <b>14 видеотренировок</b> по 25–30 мин (Drip-feed: по расписанию)\n"
            f"• <b>4 видеоурока от психолога</b> (защита от срывов и мотивация)\n"
            f"• <b>Блок «Питание»</b>: лекции нутрициолога и эндокринолога + конструктор рациона\n"
            f"• <b>Интерактивный Mini App</b> с защищенным плеером и таймером\n"
            f"• <b>AI-тренер 24/7</b> в Telegram"
        )

    await message.answer(
        text,
        reply_markup=get_persistent_reply_keyboard(),
        parse_mode="HTML"
    )
    await message.answer(
        "👇 <b>Нажмите для запуска программы:</b>",
        reply_markup=get_main_menu(has_access),
        parse_mode="HTML"
    )

@router.message(F.text.in_({"/app", "🌸 Открыть Janafit (Mini App)"}))
async def cmd_app(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌸 Запустить Janafit App", web_app={"url": f"{settings.BASE_WEB_URL}/app"})]
    ])
    await message.answer(
        "🌸 <b>Janafit Mini App готов к запуску!</b>\n\n"
        "Нажмите кнопку ниже или синюю кнопку <b>«Меню»</b> в нижнем левом углу для запуска плеера тренировок и дневника питания.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(F.text == "🤖 AI-Тренер 24/7")
async def cmd_reply_coach(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Открыть диалог с тренером", callback_data="ai_coach_start")]
    ])
    await message.answer(
        "🤖 <b>AI-тренер Janafit на связи!</b> 🌸\n\n"
        "Задайте любой вопрос по тренировкам или надиктуйте голосом/пришлите фото еды прямо в этот чат!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(F.text == "📚 Мои тренировки")
async def cmd_reply_lessons(message: Message):
    has_access = await check_user_access(message.from_user.id)
    if has_access:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть Web-плеер", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
            [InlineKeyboardButton(text="📚 Список уроков в чате", callback_data="open_course")]
        ])
        await message.answer("Выберите удобный формат тренировок:", reply_markup=keyboard)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🔥 Забрать курс за {settings.COURSE_PRICE:,} ₸", callback_data="buy_course")],
            [InlineKeyboardButton(text="🎬 Демо-уроки (Mini App)", web_app={"url": f"{settings.BASE_WEB_URL}/app"})]
        ])
        await message.answer("Вам доступен демо-режим. Открыть тренировки:", reply_markup=keyboard)

@router.callback_query(F.data == "free_workouts")
async def cb_free_workouts(callback: CallbackQuery):
    text = (
        "🎁 <b>2 БЕСПЛАТНЫЕ ТРЕНИРОВКИ (ТЕСТ-ДРАЙВ JANAFIT)</b>\n\n"
        "Мы открыли для вас доступ к первым двум полноценным урокам, чтобы вы оценили качество звука, "
        "света и методику тренера Айтыма Жакупова:\n\n"
        "<b>Урок 1: Пробуждение и лимфодренаж Full Body (20 мин)</b>\n"
        "• Снятие утренней отёчности\n"
        "• Мягкая суставная гимнастика и диафрагмальное дыхание\n\n"
        "<b>Урок 2: Осанка и здоровая спина (22 мин)</b>\n"
        "• Раскрытие грудного отдела и снятие зажимов лопаток\n"
        "• Укрепление мышечного корсета без осевой нагрузки\n\n"
        "💡 <i>Откройте Mini App, чтобы запустить тренировку с таймером и видео!</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Запустить Урок 1 в Mini App", web_app={"url": f"{settings.BASE_WEB_URL}/app?day=1"})],
        [InlineKeyboardButton(text="▶️ Запустить Урок 2 в Mini App", web_app={"url": f"{settings.BASE_WEB_URL}/app?day=2"})],
        [InlineKeyboardButton(text=f"🔥 Получить все 14 уроков за {settings.COURSE_PRICE:,} ₸", callback_data="buy_course")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "aitym_reels")
async def cb_aitym_reels(callback: CallbackQuery):
    text = (
        "🎬 <b>СОВЕТЫ АЙТЫМА ЖАКУПОВА (МИКРО-КОНТЕНТ)</b>\n\n"
        "Короткие ролики до 1 минуты, которые помогут не сорваться и получить максимум от тренировок:\n\n"
        "1. <b>«Почему диеты не работают без движения»</b>\n"
        "2. <b>«Как убрать живот за счёт дыхания, а не скручиваний»</b>\n"
        "3. <b>«Главная ошибка при боли в пояснице»</b>\n\n"
        "👉 Смотрите разборы и практикуйтесь каждый день вместе с марафоном Janafit!"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Открыть видео в Mini App", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
        [InlineKeyboardButton(text=f"🔥 Участвовать в марафоне ({settings.COURSE_PRICE:,} ₸)", callback_data="buy_course")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "about_course")
async def cb_about_course(callback: CallbackQuery):
    text = (
        f"📋 <b>ПРОГРАММА МАРАФОНА JANAFIT (14 ДНЕЙ)</b>\n\n"
        f"<b>1. Основная программа тренировок:</b>\n"
        f"• 14 авторских видеоуроков по 25–30 минут\n"
        f"• Drip-feed модель (уроки открываются постепенно, исключая перегрузку)\n"
        f"• Без прыжков и тяжелых весов — безопасно для коленей и спины\n\n"
        f"<b>2. Блок Психологии (4 видеоурока):</b>\n"
        f"• Открываются в ключевые, эмоционально сложные дни\n"
        f"• Проработка срывов, эмоционального переедания и мотивации\n\n"
        f"<b>3. Блок «Питание» (Медицинский блок):</b>\n"
        f"• Лекции нутрициолога и врача-эндокринолога\n"
        f"• Конструктор здоровой тарелки и нормы гидратации\n\n"
        f"⏱ <i>Доступ 24/7 в Telegram Mini App с защищенным плеером и таймером!</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Принять участие за {settings.COURSE_PRICE:,} ₸", callback_data="buy_course")],
        [InlineKeyboardButton(text="🎁 Попробовать 2 урока бесплатно", callback_data="free_workouts")],
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
