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
# >>> ВИПРАВЛЕННЯ: використовуємо Union для сумісності з Python 3.9
from typing import List, Dict, Any, Union 

from config import settings
import database as db
import s3_storage

router = Router()
logging.basicConfig(level=logging.INFO)

# --- FSM СТАНИ ---
# ... (всі стани ClientStates) ...
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
# ... (функції create_edit_keyboard, clean_phone_number, format_client_info) ...

# ВИПРАВЛЕНА ФУНКЦІЯ: ВИКОРИСТОВУЄ Union[]
async def find_face_match(bot: Bot, photo_file_id: str) -> Union[Dict[str, Any], None]:
    """Завантажує фото, робить енкодинг та шукає збіг у БД."""
    
    # ... (весь код, як був) ...

    photo_file = await bot.get_file(photo_file_id)
    photo_buffer = BytesIO()
    await bot.download_file(photo_file.file_path, photo_buffer) 
    photo_buffer.seek(0)
    
    # 1. Створення енкодингу для вхідного фото
    try:
        input_image = face_recognition.load_image_file(photo_buffer)
        input_encodings = face_recognition.face_encodings(input_image)
        if not input_encodings:
            return None 
        
        input_encoding = input_encodings[0]
    except Exception as e:
        logging.error(f"Face recognition failed: {e}")
        return None

    # 2. Порівняння з БД
    known_clients = await db.get_all_encodings()
    known_encodings = [np.array(c['encoding']) for c in known_clients]
    
    if known_encodings:
        matches = face_recognition.compare_faces(known_encodings, input_encoding, tolerance=0.6)
        
        for i, is_match in enumerate(matches):
            if is_match:
                return known_clients[i] 
    
    return None

# --- ЛОГІКА FSM (add_client, process_photo_for_add, process_phone, process_comment_and_save) ---
# ... (весь код FSM далі не змінюється) ...
# ... (обробники F.text та F.photo) ...
