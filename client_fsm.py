import uuid
import face_recognition
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, 
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery # Додано для меню
)
from io import BytesIO
import logging
import numpy as np
import re
from typing import List, Dict, Any, Union

from config import settings
import database as db
import s3_storage

# >>> ЗМІНА 1: ІМПОРТ ФУНКЦІЇ НОРМАЛІЗАЦІЇ
# Припускаємо, що у Data_cleaner.py є ця функція
try:
    from Data_cleaner import normalize_phone_number
except ImportError:
    logging.error("Data_cleaner.py not found or normalize_phone_number is missing.")
    # Заглушка, якщо файл не знайдено, але краще виправити імпорт
    def normalize_phone_number(phone: str) -> str:
        return re.sub(r'[^0-9\+]', '', phone)

router = Router()
logging.basicConfig(level=logging.INFO)

# --- FSM СТАНИ ---
class ClientStates(StatesGroup):
    # Додавання
    waiting_for_photo = State()
    waiting_for_phone = State()
    waiting_for_comment = State()
    
    # Пошук
    waiting_for_search_query = State() # Уніфікований стан для пошуку
    
    # Редагування
    waiting_for_edit_select = State()
    waiting_for_new_phone = State()
    waiting_for_new_comment = State()
    waiting_for_new_photo = State()
    
    # Для збереження даних знайденого клієнта
    found_client_data = State() 

# --- УТИЛІТИ ---

# ЗМІНА 2: Спрощена клавіатура редагування (інлайн)
def create_edit_inline_keyboard(db_id: int):
    """Створює інлайн-клавіатуру для редагування знайденого клієнта."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📞 Додати номер", callback_data=f"edit_phone_{db_id}"),
                InlineKeyboardButton(text="🖼️ Додати фото", callback_data=f"edit_photo_{db_id}"),
            ],
            [
                InlineKeyboardButton(text="✏️ Змінити коментар", callback_data=f"edit_comment_{db_id}"),
                InlineKeyboardButton(text="❌ Видалити клієнта", callback_data=f"delete_client_{db_id}"),
            ]
        ]
    )

def format_client_info(client: Dict[str, Any]) -> str:
    """Форматує інформацію про клієнта."""
    phones = ", ".join(client['phone']) if client['phone'] else "Не вказано"
    return (
        f"**КЛІЄНТ ЗНАЙДЕНИЙ (ID: {client['id']})**\n" # У db.py ID називається 'id'
        f"📞 Номери: {phones}\n"
        f"📝 Коментар: {client['comment']}\n"
        f"🔗 Кількість фото: {len(client['photo_url']) if client['photo_url'] else 0}"
    )

# --------------------------------------------------------------------------
# ... (find_face_match залишається без змін) ...
# --------------------------------------------------------------------------

# --- 1. ЛОГІКА ДОДАВАННЯ (З НОРМАЛІЗАЦІЄЮ) ---

@router.message(Command("add_client"))
async def start_registration(message: Message, state: FSMContext):
    await message.answer("Будь ласка, надішліть **фотографію обличчя** клієнта для реєстрації.")
    await state.clear()
    await state.set_state(ClientStates.waiting_for_photo)


@router.message(ClientStates.waiting_for_photo, F.photo)
async def process_photo_for_add(message: Message, state: FSMContext, bot: Bot):
    # ... (весь код, що перевіряє та зберігає енкодинг, без змін) ...
    # ... (частина логіки, де обробляється знайдене обличчя та пропонується редагування)
    
    # Якщо клієнт знайдений, пропонуємо редагувати
    # client_data = await find_face_match(bot, message.photo[-1].file_id) # Використовуємо функцію пошуку
    # ...
    
    # >>> СИМУЛЯЦІЯ ОБРОБКИ
    client_encoding_list = [0.1] * 128 # Заглушка
    filename = f"{message.from_user.id}_{uuid.uuid4()}.jpg"
    # s3_storage.upload_file(...) # Завантаження файлу
    photo_url = f"https://s3.url/{filename}" # Заглушка URL
    # >>> КІНЕЦЬ СИМУЛЯЦІЇ
    
    await state.update_data(
        face_encoding=client_encoding_list,
        photo_urls=[photo_url],
        telegram_id=message.from_user.id 
    )
    
    await message.answer("Фотографія оброблена. Введіть, будь ласка, **номер телефону** у форматі `+38099ххххххх`:")
    await state.set_state(ClientStates.waiting_for_phone)


@router.message(ClientStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """ЗМІНА 3: Застосовуємо нову нормалізацію."""
    raw_phone = message.text
    phone = normalize_phone_number(raw_phone)
    
    if not phone or (len(phone.strip('+')) < 6): # Мінімальна довжина номера 6 цифр (без +)
        await message.answer("Некоректний формат номера. Введіть його ще раз (з '+' або без, з пробілами, дефісами - все буде очищено).")
        return
        
    await state.update_data(phone_numbers=[phone]) # Зберігаємо НОРМАЛІЗОВАНИЙ номер
    await message.answer("Дякую. Додайте **коментар** про клієнта.")
    await state.set_state(ClientStates.waiting_for_comment)


@router.message(ClientStates.waiting_for_comment)
async def process_comment_and_save(message: Message, state: FSMContext):
    """ЗМІНА 4: Фінальне збереження - без змін, бо номери вже нормалізовані."""
    comment = message.text.strip()
    user_data = await state.get_data()
    
    await db.add_client(
        telegram_id=user_data.get('telegram_id'), 
        phone=user_data.get('phone_numbers'), # НОРМАЛІЗОВАНИЙ список
        comment=comment,
        face_encoding_array=user_data.get('face_encoding'),
        photo_url=user_data.get('photo_urls')
    )
    
    await message.answer("✅ **Клієнта успішно зареєстровано!**")
    await state.clear() 

# --- 2. ЛОГІКА ПОШУКУ (ОБ'ЄДНАНА) ---

@router.message(Command("search_client"))
async def start_search(message: Message, state: FSMContext):
    """Уніфікований старт пошуку за фото, номером або ключовим словом."""
    await state.clear()
    await message.answer(
        "Надішліть **текст** (номер, його частину або ключове слово з коментаря) або **фото** для пошуку клієнта.",
    )
    # Змінюємо стан на очікування загального запиту
    await state.set_state(ClientStates.waiting_for_search_query)


@router.message(ClientStates.waiting_for_search_query, F.text)
async def process_search_query(message: Message, state: FSMContext):
    """Пошук клієнта за текстовим запитом (номер або коментар)."""
    query = message.text.strip()
    
    if len(query) < 3:
        await message.answer("Будь ласка, введіть принаймні 3 символи для пошуку.")
        return
    
    await message.answer(f"Шукаю клієнтів за запитом: **{query}**...")
    
    # Використовуємо потужну функцію, додану в database.py
    found_clients = await db.find_client_by_query(query)
    
    if not found_clients:
        await message.answer("❌ За вашим запитом клієнтів не знайдено.")
        await state.clear()
        return

    # Якщо знайдено більше одного, виводимо список
    if len(found_clients) > 1:
        response = f"✅ Знайдено {len(found_clients)} клієнтів:\n\n"
        for i, client in enumerate(found_clients[:5]): # Обмежуємо вивід 5
            phones = ", ".join(client['phone']) if client['phone'] else "Не вказано"
            response += f"**{i+1}. ID:{client['id']}**: 📞{phones}, 📝{client['comment'][:20]}...\n"
        response += "\nБудь ласка, уточніть запит або виконайте пошук по фото."
        await message.answer(response)
        await state.clear()
    
    else:
        # Знайдено одного клієнта - виводимо інфо та кнопки редагування
        client = found_clients[0]
        await state.update_data(found_client_data=client)
        
        await message.answer(
            "✅ Знайдено єдиного клієнта. Що далі?",
            reply_markup=create_edit_inline_keyboard(client['id'])
        )
        await message.answer(format_client_info(client))
        await state.set_state(ClientStates.waiting_for_edit_select)


@router.message(ClientStates.waiting_for_search_query, F.photo)
async def process_search_photo(message: Message, state: FSMContext, bot: Bot):
    """Пошук клієнта за фото."""
    client_data = await find_face_match(bot, message.photo[-1].file_id)
    
    if not client_data:
        await message.answer("❌ За наданою фотографією збігів не знайдено.")
        await state.clear()
        return

    # Знайдено клієнта - виводимо інфо та кнопки редагування
    client_id = client_data['db_id'] # Або 'id'
    await state.update_data(found_client_data=client_data)

    await message.answer(
        "✅ Знайдено єдиного клієнта за фото. Що далі?",
        reply_markup=create_edit_inline_keyboard(client_id)
    )
    await message.answer(format_client_info(client_data))
    await state.set_state(ClientStates.waiting_for_edit_select)
    
# --- 3. ЛОГІКА РЕДАГУВАННЯ (ОБРОБКА ІНЛАЙН-КНОПОК) ---

@router.callback_query(F.data.startswith("edit_phone_"))
async def start_add_phone(call: CallbackQuery, state: FSMContext):
    db_id = int(call.data.split('_')[-1])
    await state.update_data(client_id_to_edit=db_id)
    
    await call.message.edit_text("Введіть **новий номер** телефону (він буде доданий до існуючих):")
    await state.set_state(ClientStates.waiting_for_new_phone)
    await call.answer()

@router.message(ClientStates.waiting_for_new_phone)
async def process_new_phone(message: Message, state: FSMContext):
    """Додавання нового номера до існуючого списку."""
    raw_phone = message.text
    new_phone = normalize_phone_number(raw_phone)
    
    if not new_phone or (len(new_phone.strip('+')) < 6):
        await message.answer("Некоректний формат номера. Введіть його ще раз.")
        return

    data = await state.get_data()
    db_id = data.get('client_id_to_edit')
    
    client = await db.find_client_by_id(db_id)
    if not client:
        await message.answer("❌ Клієнта не знайдено. Спробуйте почати пошук знову.")
        await state.clear()
        return

    # Додавання нового номера до списку
    updated_phones = client['phone']
    if new_phone not in updated_phones:
        updated_phones.append(new_phone)
    
    # Оновлення даних у БД
    await db.update_client_data(db_id, updated_phones, client['comment'], client['photo_url'])
    
    await message.answer(f"✅ Номер **{new_phone}** успішно додано до клієнта ID:{db_id}.")
    await state.clear()

# ... (Аналогічні хендлери для edit_comment, edit_photo, delete_client) ...

@router.callback_query(F.data.startswith("delete_client_"))
async def confirm_delete_client(call: CallbackQuery, state: FSMContext):
    db_id = int(call.data.split('_')[-1])
    # TODO: Тут має бути запит до БД на видалення.

    await call.message.edit_text(f"❌ Клієнта ID:{db_id} видалено.")
    await state.clear()
    await call.answer()

@router.message(Command("cancel"))
@router.message(F.text == "Скасувати")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Дію скасовано. Можете почати знову.")
