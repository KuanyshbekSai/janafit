import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import settings
from database import create_payment, check_user_access
from services.kaspi import get_kaspi_instructions
from services.robokassa import generate_robokassa_link

router = Router()

class CheckoutStates(StatesGroup):
    waiting_for_receipt = State()

@router.callback_query(F.data == "buy_course")
async def cb_buy_course(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await check_user_access(user_id):
        await callback.message.answer("🎉 У вас уже есть активный доступ к курсу! Открывайте тренировки.")
        await callback.answer()
        return

    text = (
        f"💳 <b>Оформление доступа к курсу Janafit</b>\n\n"
        f"📦 Товар: <b>{settings.COURSE_TITLE}</b>\n"
        f"🔥 Сумма со скидкой: <b>{settings.COURSE_PRICE:,} ₸</b> <s>{settings.COURSE_ORIGINAL_PRICE:,} ₸</s>\n\n"
        f"Выберите удобный способ оплаты:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟡 Kaspi (QR / Перевод / Kaspi Pay)", callback_data="pay_kaspi")],
        [InlineKeyboardButton(text="💳 Банковская карта (Robokassa / Visa / MC)", callback_data="pay_robokassa")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "pay_robokassa")
async def cb_pay_robokassa(callback: CallbackQuery):
    user_id = callback.from_user.id
    invoice_id = f"JF-{int(user_id % 100000)}-{uuid.uuid4().hex[:6].upper()}"

    await create_payment(
        invoice_id=invoice_id,
        user_id=user_id,
        amount=settings.COURSE_PRICE,
        provider="robokassa"
    )

    pay_url = generate_robokassa_link(
        invoice_id=invoice_id,
        amount=settings.COURSE_PRICE,
        description=f"Janafit Course Access #{invoice_id}",
        user_id=user_id
    )

    text = (
        f"💳 <b>Оплата банковской картой (Robokassa)</b>\n\n"
        f"Сумма: <b>{settings.COURSE_PRICE:,} ₸</b>\n"
        f"Номер заказа: <code>{invoice_id}</code>\n\n"
        f"Нажмите кнопку ниже, чтобы перейти на защищенную страницу оплаты. "
        f"После завершения платежа доступ откроется автоматически за пару секунд!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Перейти к оплате картой", url=pay_url)],
        [InlineKeyboardButton(text="◀️ Выбрать другой способ", callback_data="buy_course")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "pay_kaspi")
async def cb_pay_kaspi(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    invoice_id = f"KASPI-{uuid.uuid4().hex[:6].upper()}"

    payment_id = await create_payment(
        invoice_id=invoice_id,
        user_id=user_id,
        amount=settings.COURSE_PRICE,
        provider="kaspi"
    )

    await state.update_data(current_invoice_id=invoice_id, current_payment_id=payment_id)
    await state.set_state(CheckoutStates.waiting_for_receipt)

    instructions = get_kaspi_instructions(invoice_id, settings.COURSE_PRICE)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Выбрать другой способ", callback_data="buy_course")]
    ])

    await callback.message.edit_text(instructions, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(CheckoutStates.waiting_for_receipt, F.photo | F.document)
async def process_receipt(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()
    invoice_id = data.get("current_invoice_id", "UNKNOWN")
    payment_id = data.get("current_payment_id", 0)

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    await state.clear()

    await message.answer(
        "⏳ <b>Ваш чек принят на проверку!</b>\n\n"
        "Куратор или автоматическая система проверяет поступление. Обычно это занимает от 1 до 5 минут.\n"
        "Как только оплата подтвердится, вы получите персональную ссылку в закрытый канал и уроки!",
        parse_mode="HTML"
    )

    # Уведомляем кураторов / админов
    admin_targets = [settings.SUPPORT_CHAT_ID] if settings.SUPPORT_CHAT_ID else settings.admin_id_list

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить и выдать доступ", callback_data=f"adm_approve:{payment_id}:{user_id}:{invoice_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_reject:{payment_id}:{user_id}")
        ]
    ])

    caption = (
        f"🔔 <b>Новая оплата Kaspi на проверку!</b>\n\n"
        f"👤 Клиент: @{message.from_user.username or 'без_юзернейма'} (ID: <code>{user_id}</code>)\n"
        f"Имя: {message.from_user.full_name}\n"
        f"Заказ: <code>{invoice_id}</code>\n"
        f"Сумма: <b>{settings.COURSE_PRICE:,} ₸</b>"
    )

    for target in admin_targets:
        if not target:
            continue
        try:
            if message.photo:
                await bot.send_photo(chat_id=target, photo=file_id, caption=caption, reply_markup=admin_keyboard, parse_mode="HTML")
            else:
                await bot.send_document(chat_id=target, document=file_id, caption=caption, reply_markup=admin_keyboard, parse_mode="HTML")
        except Exception as e:
            pass
