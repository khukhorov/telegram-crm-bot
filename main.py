import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton 

from config import settings
import database as db
import s3_storage 
import client_fsm as cfsm # <<< ІМПОРТУЄМО РОУТЕР

logging.basicConfig(level=logging.INFO)

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# --- Створення Клавіатури Меню ---
MENU_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/add_client")],
        [KeyboardButton(text="/search_client")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# --- ОСНОВНІ ОБРОБНИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обробник команди /start. Відправляє головне меню."""
    await message.answer(
        "Вітаю! CRM-бот запущено, база даних PostgreSQL підключена. Виберіть дію:",
        reply_markup=MENU_KEYBOARD 
    )

# ... (інші заглушки тут можна прибрати, оскільки вони в cfsm.py) ...

async def main():
    """Головна функція запуску бота."""
    try:
        await db.init_db() 
    except Exception:
        logging.error("Критична помилка: Не вдалося підключитися до бази даних. Бот не запускається.")
        return
        
    # КРИТИЧНО ВАЖЛИВО: ВКЛЮЧАЄМО РОУТЕР З FSM ЛОГІКОЮ
    dp.include_router(cfsm.router) 

    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
