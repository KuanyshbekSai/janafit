from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import settings
from database import get_sales_stats, mark_payment_success, grant_user_access

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_id_list

@router.message(F.text.in_(["/admin", "/stats"]))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await get_sales_stats()
    text = (
        f"📊 <b>Панель управления Janafit</b>\n\n"
        f"👥 Всего пользователей в боте: <b>{stats['total_users']}</b>\n"
        f"💎 Учениц с активным доступом: <b>{stats['active_students']}</b>\n"
        f"💰 Оплаченных заказов: <b>{stats['success_payments']}</b>\n"
        f"💵 Суммарная выручка: <b>{stats['total_revenue']:,} ₸</b>\n"
        f"⏳ Платежей на проверке: <b>{stats['pending_payments']}</b>\n\n"
        f"⚡️ Оффер: <b>{settings.COURSE_PRICE:,} ₸</b>"
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_approve:"))
async def cb_admin_approve(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id) and callback.message.chat.id != settings.SUPPORT_CHAT_ID:
        await callback.answer("У вас нет прав администратора", show_alert=True)
        return

    parts = callback.data.split(":")
    payment_id = int(parts[1])
    user_id = int(parts[2])
    invoice_id = parts[3]

    await mark_payment_success(invoice_id)
    await grant_user_access(user_id)

    # Генерируем инвайт-ссылку для клиента
    invite_link = None
    if settings.PRIVATE_CHANNEL_ID:
        try:
            link_obj = await bot.create_chat_invite_link(
                chat_id=settings.PRIVATE_CHANNEL_ID,
                member_limit=1,
                name=f"Janafit_Auto_{user_id}"
            )
            invite_link = link_obj.invite_link
        except Exception:
            pass

    # Отправляем сообщение пользователю
    user_text = (
        f"🎉 <b>Ура! Ваша оплата подтверждена!</b>\n\n"
        f"Вам открыт полный доступ к курсу <b>«{settings.COURSE_TITLE}»</b>.\n\n"
        f"Прямо сейчас вы можете приступить к первой тренировке и вступить в закрытый VIP-клуб:"
    )

    buttons = []
    if invite_link:
        buttons.append([InlineKeyboardButton(text="💎 Вступить в Закрытый Канал", url=invite_link)])
    buttons.append([InlineKeyboardButton(text="▶️ Открыть тренировки в боте", callback_data="open_course")])
    buttons.append([InlineKeyboardButton(text="📱 Запустить Web-плеер (Mini App)", web_app={"url": f"{settings.BASE_WEB_URL}/app"})])

    try:
        await bot.send_message(
            chat_id=user_id,
            text=user_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Обновляем сообщение у админа
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Одобрено ({callback.from_user.first_name})", callback_data="none")]
    ]))
    await callback.answer("Доступ успешно выдан!")

@router.callback_query(F.data.startswith("adm_reject:"))
async def cb_admin_reject(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id) and callback.message.chat.id != settings.SUPPORT_CHAT_ID:
        await callback.answer("У вас нет прав администратора", show_alert=True)
        return

    parts = callback.data.split(":")
    user_id = int(parts[2])

    try:
        await bot.send_message(
            chat_id=user_id,
            text="⚠️ <b>Чек не прошел верификацию.</b>\nПожалуйста, убедитесь, что перевод прошел успешно, или свяжитесь с куратором через меню.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❌ Отклонено ({callback.from_user.first_name})", callback_data="none")]
    ]))
    await callback.answer("Платеж отклонен")
