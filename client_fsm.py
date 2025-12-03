import uuid
import face_recognition
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from io import BytesIO
import logging
import numpy as np
import re
from typing import List, Dict, Any

from config import settings
import database as db
import s3_storage

router = Router()
logging.basicConfig(level=logging.INFO)

# --- FSM СТАНИ ---
class ClientStates(StatesGroup):
    # Додавання
    waiting_for_photo = State()
    waiting_for_phone = State()
    waiting_for_comment = State()
    
    # Пошук
    waiting_for_search_photo = State()
    waiting_for_search_phone = State()
    waiting_for_search_keyword = State()
    
    # Редагування
    waiting_for_edit_select = State()
    waiting_for_new_phone = State()
    waiting_for_new_comment = State()
    waiting_for_new_photo = State()
    
    # Для збереження даних знайденого клієнта
    found_client_data = State() 

# --- УТИЛІТИ ---

def create_edit_keyboard():
    """Створює клавіатуру для редагування клієнта."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Додати номер"), KeyboardButton(text="Редагувати коментар")],
            [KeyboardButton(text="Додати фото"), KeyboardButton(text="Скасувати редагування")]
        ],
        resize_keyboard=True
    )

def clean_phone_number(phone: str) -> str:
    """Очищує та валідує номер телефону."""
    phone = re.sub(r'[^\d+]', '', phone).replace(' ', '')
    if not re.match(r'^\+\d{6,15}$', phone):
        return None
    return phone

def format_client_info(client: Dict[str, Any]) -> str:
    """Форматує інформацію про клієнта."""
    phones = ", ".join(client['phone']) if client['phone'] else "Не вказано"
    return (
        f"**КЛІЄНТ ЗНАЙДЕНИЙ (ID: {client['db_id']})**\n"
        f"📞 Номери: {phones}\n"
        f"📝 Коментар: {client['comment']}\n"
        f"🔗 Кількість фото: {len(client['photo_url']) if client['photo_url'] else 0}"
    )

async def find_face_match(bot: Bot, photo_file_id: str) -> Dict[str, Any] | None:
    """Завантажує фото, робить енкодинг та шукає збіг у БД."""
    # (Ця частина є найскладнішою і вимагає повного, коректного коду face_recognition)
    # Через обмеження face_recognition у деяких середовищах, тут буде спрощена логіка:
    
    photo_file = await bot.get_file(photo_file_id)
    photo_buffer = BytesIO()
    await bot.download_file(photo_file.file_path, photo_buffer) 
    photo_buffer.seek(0)
    
    # 1. Створення енкодингу для вхідного фото
    try:
        # Для коректної роботи face_recognition тут потрібні numpy та dlib
        input_image = face_recognition.load_image_file(photo_buffer)
        input_encodings = face_recognition.face_encodings(input_image)
        if not input_encodings:
            return None # Обличчя не знайдено
        
        input_encoding = input_encodings[0]
    except Exception as e:
        logging.error(f"Face recognition failed: {e}")
        return None

    # 2. Порівняння з БД
    known_clients = await db.get_all_encodings()
    known_encodings = [np.array(c['encoding']) for c in known_clients]
    
    if known_encodings:
        # Порівняння з усіма відомими обличчями
        matches = face_recognition.compare_faces(known_encodings, input_encoding, tolerance=0.6)
        
        for i, is_match in enumerate(matches):
            if is_match:
                return known_clients[i] # Повертаємо знайденого клієнта
    
    return None

# --- 1. ЛОГІКА ДОДАВАННЯ ---

@router.message(Command("add_client"))
async def start_registration(message: Message, state: FSMContext):
    """Початок реєстрації клієнта."""
    await message.answer("Будь ласка, надішліть **фотографію обличчя** клієнта для реєстрації.")
    await state.clear()
    await state.set_state(ClientStates.waiting_for_photo)


@router.message(ClientStates.waiting_for_photo, F.photo)
async def process_photo_for_add(message: Message, state: FSMContext, bot: Bot):
    """Обробка фото: енкодинг та завантаження в Spaces."""
    await message.answer("Обробляю фото, зачекайте...")
    
    # 1. Обробка обличчя та енкодинг
    client_data = await find_face_match(bot, message.photo[-1].file_id) # Використовуємо функцію пошуку
    
    if client_data:
        # Якщо клієнт знайдений, пропонуємо редагувати
        await message.answer("⚠️ **ОБЕРЕЖНО:** Схоже, цей клієнт вже є у базі. Ви хочете його редагувати? \n\n" + format_client_info(client_data), reply_markup=create_edit_keyboard())
        await state.update_data(found_client_data=client_data)
        await state.set_state(ClientStates.waiting_for_edit_select)
        return
        
    # Якщо не знайдений, продовжуємо додавання
    # ... (ПОВНА ЛОГІКА ЗБЕРЕЖЕННЯ ЕНКОДИНГУ ТА URL У state)
    
    # >>> СИМУЛЯЦІЯ ОБРОБКИ
    client_encoding_list = [0.1] * 128 # Заглушка
    filename = f"{message.from_user.id}_{uuid.uuid4()}.jpg"
    photo_url = s3_storage.get_photo_url(filename) # Заглушка URL
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
    phone = clean_phone_number(message.text)
    if not phone:
        await message.answer("Некоректний формат номера. Введіть його ще раз у форматі `+хххххххххххххххх` (без пробілів).")
        return
        
    await state.update_data(phone_numbers=[phone]) 
    await message.answer("Дякую. Додайте **коментар** про клієнта.")
    await state.set_state(ClientStates.waiting_for_comment)


@router.message(ClientStates.waiting_for_comment)
async def process_comment_and_save(message: Message, state: FSMContext):
    comment = message.text.strip()
    user_data = await state.get_data()
    
    await db.add_client(
        telegram_id=user_data.get('telegram_id'), 
        phone=user_data.get('phone_numbers'),
        comment=comment,
        face_encoding_array=user_data.get('face_encoding'),
        photo_url=user_data.get('photo_urls')
    )
    
    await message.answer("✅ **Клієнта успішно зареєстровано!** \n\n Тепер ви можете його знайти за допомогою команди /search_client.")
    await state.clear() 

# --- 2. ЛОГІКА ПОШУКУ (ЗАГЛУШКИ) ---

@router.message(Command("search_client"))
async def start_search(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Виберіть тип пошуку:", 
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="/search_photo"), KeyboardButton(text="/search_phone")],
                [KeyboardButton(text="/search_keyword")]
            ],
            resize_keyboard=True
        )
    )

@router.message(Command("search_photo"))
async def start_search_photo(message: Message, state: FSMContext):
    await message.answer("Надішліть фото для порівняння облич.")
    await state.set_state(ClientStates.waiting_for_search_photo)

# ... (інші обробники пошуку по номеру/коментарю)

# --- 3. ЛОГІКА РЕДАГУВАННЯ (ЗАГЛУШКИ) ---

@router.message(ClientStates.waiting_for_edit_select, F.text == "Скасувати редагування")
async def cancel_edit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Редагування скасовано.")

@router.message(Command("edit_client"))
async def cmd_edit_start(message: Message):
    await message.answer("Для редагування вам потрібно спочатку знайти клієнта за допомогою команди /search_client.")
