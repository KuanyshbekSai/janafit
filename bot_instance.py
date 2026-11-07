from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings

bot = Bot(token=settings.BOT_TOKEN or "123456:PLACEHOLDER_TOKEN")
dp = Dispatcher(storage=MemoryStorage())
