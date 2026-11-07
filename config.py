import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List

BASE_DIR = Path(__file__).resolve().parent

def _int_env(key: str, default: int) -> int:
    val = os.getenv(key, "")
    if not val or not str(val).strip():
        return default
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default

def _resolve_db_path() -> str:
    env_path = os.getenv("DB_PATH")
    if env_path and env_path.strip():
        return env_path.strip()
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
    PRIVATE_CHANNEL_ID: int = _int_env("PRIVATE_CHANNEL_ID", 0)
    SUPPORT_CHAT_ID: int = _int_env("SUPPORT_CHAT_ID", 0)

    # Offer
    COURSE_PRICE: int = _int_env("COURSE_PRICE", 4990)
    COURSE_ORIGINAL_PRICE: int = _int_env("COURSE_ORIGINAL_PRICE", 8900)
    COURSE_TITLE: str = os.getenv("COURSE_TITLE", "Janafit: Перезагрузка и Стройность (21 день)")

    # Robokassa
    ROBOKASSA_LOGIN: str = os.getenv("ROBOKASSA_LOGIN", "")
    ROBOKASSA_PASSWORD_1: str = os.getenv("ROBOKASSA_PASSWORD_1", "")
    ROBOKASSA_PASSWORD_2: str = os.getenv("ROBOKASSA_PASSWORD_2", "")
    ROBOKASSA_IS_TEST: int = _int_env("ROBOKASSA_IS_TEST", 1)

    # Kaspi
    KASPI_PHONE: str = os.getenv("KASPI_PHONE", "+7 (777) 000-00-00")
    KASPI_PAY_LINK: str = os.getenv("KASPI_PAY_LINK", "")
    KASPI_QR_IMAGE_PATH: str = os.getenv("KASPI_QR_IMAGE_PATH", "data/kaspi_qr.png")

    # AI Coach
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Web & Webhook Server
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = _int_env("WEB_PORT", 8000)
    BASE_WEB_URL: str = os.getenv("BASE_WEB_URL", "http://localhost:8000")

    # Database (на Vercel файловая система read-only, доступна только /tmp)
    DB_PATH: str = _resolve_db_path()

    @field_validator(
        "PRIVATE_CHANNEL_ID",
        "SUPPORT_CHAT_ID",
        "COURSE_PRICE",
        "COURSE_ORIGINAL_PRICE",
        "ROBOKASSA_IS_TEST",
        "WEB_PORT",
        mode="before"
    )
    @classmethod
    def parse_int_fields(cls, v, info):
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            defaults = {
                "PRIVATE_CHANNEL_ID": 0,
                "SUPPORT_CHAT_ID": 0,
                "COURSE_PRICE": 4990,
                "COURSE_ORIGINAL_PRICE": 8900,
                "ROBOKASSA_IS_TEST": 1,
                "WEB_PORT": 8000
            }
            return defaults.get(info.field_name, 0)
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    @field_validator("DB_PATH", mode="before")
    @classmethod
    def parse_db_path(cls, v):
        if not v or not str(v).strip():
            return _resolve_db_path()
        return str(v).strip()

    @field_validator("COURSE_TITLE", mode="before")
    @classmethod
    def parse_course_title(cls, v):
        if not v or not str(v).strip():
            return "Janafit: Перезагрузка и Стройность (21 день)"
        return str(v).strip()

    @field_validator("KASPI_PHONE", mode="before")
    @classmethod
    def parse_kaspi_phone(cls, v):
        if not v or not str(v).strip():
            return "+7 (777) 000-00-00"
        return str(v).strip()

    @field_validator("BASE_WEB_URL", mode="before")
    @classmethod
    def parse_base_web_url(cls, v):
        if not v or not str(v).strip():
            return "http://localhost:8000"
        return str(v).strip().rstrip("/")

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
