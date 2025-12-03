import asyncio
import logging
# ВАЖЛИВО: ДОДАНО F до імпортів!
from aiogram import Bot, Dispatcher, types, F 
from aiogram.filters import Command, StateFilter 
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state 
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton 

from config import settings
import database as db
import s3_storage 
import client_fsm as cfsm 

logging.basicConfig(level=logging.INFO)
# ... (решта коду без змін)


bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# --- Створення Клавіатури Меню ---
MENU_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        # Оновлені кнопки з емодзі та повним текстом
        [KeyboardButton(text="➕ Новий клієнт"), KeyboardButton(text="🔍 Пошук клієнта")],
        [KeyboardButton(text="❌ Скасувати")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# --- ОСНОВНІ ОБРОБНИКИ ---

@dp.message(Command("start"), StateFilter(default_state))
async def cmd_start(message: types.Message):
    """Обробник команди /start. Відправляє головне меню."""
    await message.answer(
        "Вітаю! CRM-бот запущено, база даних PostgreSQL підключена. Виберіть дію:",
        reply_markup=MENU_KEYBOARD 
    )

@dp.message(Command("cancel"), ~StateFilter(default_state))
@dp.message(F.text.lower() == "скасувати", ~StateFilter(default_state))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """
    ЗМІНА 1: Обробник команди /cancel або кнопки 'Скасувати' для виходу зі стану FSM.
    Працює, лише якщо бот НЕ перебуває у default_state.
    """
    await state.clear()
    await message.answer(
        "Дія скасована. Повертаємося до головного меню.",
        reply_markup=MENU_KEYBOARD 
    )


async def main():
    """Головна функція запуску бота."""
    # 1. Ініціалізація БД
    try:
        await db.init_db() 
        # Якщо використовуєте s3_storage, його ініціалізацію можна додати тут
        # s3_storage.init_client() 
    except Exception:
        logging.error("Критична помилка: Не вдалося підключитися до бази даних. Бот не запускається.")
        return
        
    # 2. ВКЛЮЧАЄМО РОУТЕРИ
    # Роутер з FSM логікою клієнтів
    dp.include_router(cfsm.router) 
    
    # 3. Запуск
    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
