from config import settings

def get_kaspi_instructions(invoice_id: str, amount: int = None) -> str:
    amount = amount or settings.COURSE_PRICE
    phone = settings.KASPI_PHONE
    pay_link = settings.KASPI_PAY_LINK

    text = (
        f"💳 <b>Оплата через Kaspi:</b>\n\n"
        f"Сумма к оплате: <b>{amount:,} ₸</b>\n"
        f"Номер заказа: <code>{invoice_id}</code>\n\n"
        f"<b>Инструкция:</b>\n"
    )

    if pay_link:
        text += f"1️⃣ Перейдите по ссылке для быстрой оплаты: <a href='{pay_link}'>Kaspi QR / Оплата</a>\n"
    else:
        text += (
            f"1️⃣ Откройте приложение Kaspi.kz ➡️ Переводы\n"
            f"2️⃣ Переведите <b>{amount:,} ₸</b> на номер: <code>{phone}</code>\n"
            f"3️⃣ В сообщении к переводу укажите ваш номер заказа: <code>{invoice_id}</code>\n"
        )

    text += (
        f"\n4️⃣ <b>Отправьте квитанцию или скриншот чека прямо в этот чат</b>.\n\n"
        f"<i>⚡️ Как только бот получит чек, доступ к курсу откроется автоматически!</i>"
    )
    return text
