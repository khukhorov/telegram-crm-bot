import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from config import settings
import database as db
# import face_processor as fp # Тут буде логіка обробки облич

logging.basicConfig(level=logging.INFO)

# Ініціалізація
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# --- ОБРОБНИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обробник команди /start"""
    await message.answer("CRM-бот запущено! База даних PostgreSQL успішно підключена. Спробуйте /add.")

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    """Обробник команди /add (початок додавання клієнта)"""
    await message.answer("Щоб додати нового клієнта, надішліть його фотографію.")
    # Тут має бути перехід до стану FSM

@dp.message()
async def unhandled_message(message: types.Message):
    """Обробник, який ловить всі нерозпізнані повідомлення (для діагностики)"""
    if message.text:
        await message.answer(f"Невідома команда чи текст. Я не знаю, що робити з: {message.text}")
    elif message.photo:
        await message.answer("Я отримав ваше фото. Для його обробки потрібна повна логіка Face Recognition та налаштування сховища Spaces!")
    else:
        await message.answer("Я отримав нерозпізнане повідомлення.")

# ----------------------------------------

async def main():
    """Головна функція запуску бота."""
    try:
        # 1. Ініціалізація PostgreSQL
        await db.init_db() 
    except Exception:
        logging.error("Критична помилка: Не вдалося підключитися до бази даних. Бот не запускається.")
        return
        
    # 2. АІОGRAM 3.Х: Реєстрація всіх обробників, визначених у цьому файлі
    dp.include_router(dp) 

    logging.info("Starting bot polling...")
    # 3. Запуск опитування (Polling)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
