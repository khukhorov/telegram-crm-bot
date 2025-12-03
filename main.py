import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command

from config import settings # <<< ІМПОРТУЄМО НОВИЙ ФАЙЛ
import database as db

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Ініціалізація
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# --- ПРИКЛАД ОБРОБНИКА ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обробник команди /start"""
    await message.answer("CRM-бот запущено! База даних PostgreSQL успішно підключена.")
    
# --- ТУТ БУДЕ ВАШ ОБРОБНИК ФОТО та FSM ---

# ----------------------------------------

async def main():
    """Головна функція запуску бота."""
    try:
        # Ініціалізація PostgreSQL перед запуском опитування
        await db.init_db() 
    except Exception:
        logging.error("Критична помилка: Не вдалося підключитися до бази даних. Бот не запускається.")
        return

    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
