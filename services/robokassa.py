import hashlib
from urllib.parse import urlencode
from config import settings

def calculate_signature(*args) -> str:
    concatenated = ":".join(str(arg) for arg in args)
    return hashlib.md5(concatenated.encode('utf-8')).hexdigest()

def generate_robokassa_link(invoice_id: str, amount: int, description: str, user_id: int) -> str:
    """
    Генерирует ссылку для перехода на страницу оплаты Robokassa.
    """
    login = settings.ROBOKASSA_LOGIN
    password_1 = settings.ROBOKASSA_PASSWORD_1
    is_test = settings.ROBOKASSA_IS_TEST

    # Формула Robokassa: md5(mrh_login:out_sum:inv_id:pass1:shp_user_id)
    # Для простоты:
    signature = calculate_signature(login, amount, invoice_id, password_1, f"shp_user_id={user_id}")

    base_url = "https://auth.robokassa.ru/Merchant/Index.aspx"

    params = {
        "MerchantLogin": login,
        "OutSum": str(amount),
        "InvId": invoice_id,
        "Description": description,
        "SignatureValue": signature,
        "shp_user_id": str(user_id),
        "Culture": "ru"
    }

    if is_test:
        params["IsTest"] = "1"

    return f"{base_url}?{urlencode(params)}"

def verify_robokassa_webhook(out_sum: str, inv_id: str, received_signature: str, user_id: str) -> bool:
    """
    Проверяет валидность уведомления об оплате (ResultURL) от Robokassa.
    Формула: md5(out_sum:inv_id:pass2:shp_user_id)
    """
    password_2 = settings.ROBOKASSA_PASSWORD_2
    expected_signature = calculate_signature(out_sum, inv_id, password_2, f"shp_user_id={user_id}").upper()
    return expected_signature == received_signature.upper()
