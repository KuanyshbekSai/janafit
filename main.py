import asyncio
import logging
import uvicorn
from aiogram import Bot

from config import settings
from database import init_db
from bot_instance import bot, dp
from handlers import start, checkout, course, ai_coach, admin
from web.server import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("JanafitMain")

async def start_web_server():
    """Запускает веб-сервер FastAPI для вебхуков Robokassa/Kaspi и Telegram Mini App."""
    config = uvicorn.Config(
        app=app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    logger.info(f"🚀 Веб-сервер запущен на http://{settings.WEB_HOST}:{settings.WEB_PORT}")
    await server.serve()

async def start_bot():
    """Запускает поллинг Telegram бота."""
    if not settings.BOT_TOKEN or "PLACEHOLDER" in settings.BOT_TOKEN:
        logger.warning("⚠️ BOT_TOKEN не указан в .env. Бот в режиме ожидания токена.")
        return

    # Регистрация роутеров
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(checkout.router)
    dp.include_router(course.router)
    dp.include_router(ai_coach.router)

    # Удаляем старые вебхуки перед поллингом
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🤖 Бот Janafit успешно запущен в режиме polling!")
    await dp.start_polling(bot)

async def main():
    # Инициализация базы данных SQLite
    await init_db()
    logger.info("📦 База данных SQLite инициализирована.")

    # Запускаем параллельно веб-сервер и бота
    await asyncio.gather(
        start_web_server(),
        start_bot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Сервер Janafit остановлен.")
