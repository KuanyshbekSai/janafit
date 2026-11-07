import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl, unquote
from typing import Optional, Dict, Any

def validate_telegram_init_data(init_data_raw: str, bot_token: str, max_age_seconds: int = 86400) -> Optional[Dict[str, Any]]:
    """
    Валидирует криптографическую подпись данных Telegram WebApp initData по стандарту Telegram.
    Исключает подделку идентификатора пользователя и несанкционированный доступ к тренировкам.
    """
    if not init_data_raw or not bot_token:
        return None

    try:
        parsed_data = dict(parse_qsl(init_data_raw, keep_blank_values=True))
        received_hash = parsed_data.pop("hash", None)
        if not received_hash:
            return None

        # Проверка актуальности данных (auth_date)
        auth_date = int(parsed_data.get("auth_date", 0))
        if auth_date > 0 and (time.time() - auth_date > max_age_seconds):
            # Данные устарели
            return None

        # Сортировка параметров по алфавиту и сборка data_check_string
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

        # secret_key = HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

        # calculated_hash = HMAC_SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            if "user" in parsed_data:
                parsed_data["user"] = json.loads(unquote(parsed_data["user"]))
            return parsed_data
    except Exception:
        pass

    return None
