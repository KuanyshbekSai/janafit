import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

BASE_DIR = Path(__file__).resolve().parent

def _resolve_db_path() -> str:
    env_path = os.getenv("DB_PATH")
    if env_path:
        return env_path
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/janafit.db"
    try:
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return str(data_dir / "janafit.db")
    except Exception:
        return "/tmp/janafit.db"

class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: str = os.getenv("ADMIN_IDS", "")
    PRIVATE_CHANNEL_ID: int = int(os.getenv("PRIVATE_CHANNEL_ID", "0"))
    SUPPORT_CHAT_ID: int = int(os.getenv("SUPPORT_CHAT_ID", "0"))

    # Offer
    COURSE_PRICE: int = int(os.getenv("COURSE_PRICE", "4990"))
    COURSE_ORIGINAL_PRICE: int = int(os.getenv("COURSE_ORIGINAL_PRICE", "8900"))
    COURSE_TITLE: str = os.getenv("COURSE_TITLE", "Janafit: Перезагрузка и Стройность (21 день)")

    # Robokassa
    ROBOKASSA_LOGIN: str = os.getenv("ROBOKASSA_LOGIN", "")
    ROBOKASSA_PASSWORD_1: str = os.getenv("ROBOKASSA_PASSWORD_1", "")
    ROBOKASSA_PASSWORD_2: str = os.getenv("ROBOKASSA_PASSWORD_2", "")
    ROBOKASSA_IS_TEST: int = int(os.getenv("ROBOKASSA_IS_TEST", "1"))

    # Kaspi
    KASPI_PHONE: str = os.getenv("KASPI_PHONE", "+7 (777) 000-00-00")
    KASPI_PAY_LINK: str = os.getenv("KASPI_PAY_LINK", "")
    KASPI_QR_IMAGE_PATH: str = os.getenv("KASPI_QR_IMAGE_PATH", "data/kaspi_qr.png")

    # AI Coach
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Web & Webhook Server
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = int(os.getenv("WEB_PORT", "8000"))
    BASE_WEB_URL: str = os.getenv("BASE_WEB_URL", "http://localhost:8000")

    # Database (на Vercel файловая система read-only, доступна только /tmp)
    DB_PATH: str = _resolve_db_path()

    @property
    def admin_id_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
