from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import settings
from database import check_user_access, grant_user_access

router = Router()

LESSONS = [
    {"day": 1, "title": "День 1: Пробуждение и лимфодренаж", "duration": "20 мин", "focus": "Снятие отеков, дыхание диафрагмой", "yt_url": "https://youtu.be/gC_L9qAHVJ8"},
    {"day": 2, "title": "День 2: Осанка и здоровая спина", "duration": "22 мин", "focus": "Раскрытие плеч, снятие зажимов лопаток", "yt_url": "https://youtu.be/2MoGxae-zyo"},
    {"day": 3, "title": "День 3: Упругие ягодицы без приседаний", "duration": "25 мин", "focus": "Активация ягодичных без нагрузки на колени", "yt_url": "https://youtu.be/I94V6qBfF0Y"},
    {"day": 4, "title": "День 4: Плоский живот и вакуум", "duration": "18 мин", "focus": "Поперечная мышца, укрепление тазового дна", "yt_url": "https://youtu.be/ml6cT4AZdqI"},
    {"day": 5, "title": "День 5: Стройные ноги и бедра", "duration": "24 мин", "focus": "Внутренняя и задняя поверхность бедер", "yt_url": "https://youtu.be/IT94xC35u6k"},
    {"day": 6, "title": "День 6: Мягкое кардио-жиросжигание", "duration": "25 мин", "focus": "Интервальная нагрузка без прыжков", "yt_url": "https://youtu.be/UBMk30rjy0o"},
    {"day": 7, "title": "День 7: Глубокая растяжка и релакс", "duration": "25 мин", "focus": "Восстановление мышц и гибкость", "yt_url": "https://youtu.be/enYITYwv8c4"}
]

@router.message(F.text == "/demo")
async def cmd_demo(message: Message):
    """Команда для быстрого тестирования: выдает демо-доступ без оплаты."""
    await grant_user_access(message.from_user.id)
    await message.answer(
        "🎉 <b>Тестовый демо-доступ активирован!</b>\n\n"
        "Теперь вам открыты все тренировки в боте и в интерактивном Telegram Mini App.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть Mini App (Плеер + Таймер)", web_app={"url": f"{settings.BASE_WEB_URL}/app"})],
            [InlineKeyboardButton(text="📚 Список уроков в чате", callback_data="lessons_list")]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "open_course")
async def cb_open_course(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    has_access = await check_user_access(user_id)

    if not has_access:
        await callback.message.answer(
            "🔒 <b>Доступ закрыт!</b>\n\nЧтобы открыть уроки, пожалуйста, оформите курс.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Купить за {settings.COURSE_PRICE:,} ₸", callback_data="buy_course")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    invite_link = None
    if settings.PRIVATE_CHANNEL_ID:
        try:
            link_obj = await bot.create_chat_invite_link(
                chat_id=settings.PRIVATE_CHANNEL_ID,
                member_limit=1,
                name=f"Janafit_User_{user_id}"
            )
            invite_link = link_obj.invite_link
        except Exception:
            pass

    text = (
        f"🎉 <b>Добро пожаловать в закрытый клуб Janafit!</b>\n\n"
        f"Твой доступ активен. Ты можешь смотреть уроки прямо в боте, перейти в закрытый VIP-канал или запустить удобное Web-приложение:"
    )

    buttons = []
    if invite_link:
        buttons.append([InlineKeyboardButton(text="💎 Вступить в Закрытый VIP-Канал", url=invite_link)])
    
    buttons.append([InlineKeyboardButton(text="📱 Открыть Web-плеер (Mini App)", web_app={"url": f"{settings.BASE_WEB_URL}/app"})])
    buttons.append([InlineKeyboardButton(text="📚 Уроки прямо здесь (по дням)", callback_data="lessons_list")])
    buttons.append([InlineKeyboardButton(text="🤖 Задать вопрос AI-тренеру", callback_data="ai_coach_start")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "lessons_list")
async def cb_lessons_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await check_user_access(user_id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    text = "📋 <b>Список тренировок недели 1:</b>\n\nВыберите тренировку для просмотра:"
    keyboard = []
    for l in LESSONS:
        keyboard.append([InlineKeyboardButton(text=f"▶️ {l['title']} ({l['duration']})", callback_data=f"lesson:{l['day']}")])

    keyboard.append([InlineKeyboardButton(text="◀️ В меню курса", callback_data="open_course")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("lesson:"))
async def cb_view_lesson(callback: CallbackQuery):
    day = int(callback.data.split(":")[1])
    lesson = next((l for l in LESSONS if l["day"] == day), None)
    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    text = (
        f"🎬 <b>{lesson['title']}</b>\n\n"
        f"⏱ <b>Длительность:</b> {lesson['duration']}\n"
        f"🎯 <b>Фокус занятия:</b> {lesson['focus']}\n\n"
        f"💡 <i>Совет тренера: держите под рукой стакан теплой воды и полотенце. "
        f"Не забывайте дышать ровно и не задерживать дыхание.</i>\n\n"
        f"👇 Запустите видеоурок в интерактивном плеере:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Запустить тренировку", web_app={"url": f"{settings.BASE_WEB_URL}/app?day={day}"})],
        [InlineKeyboardButton(text="🤖 Вопрос по технике к AI-тренеру", callback_data="ai_coach_start")],
        [InlineKeyboardButton(text="◀️ К списку уроков", callback_data="lessons_list")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
