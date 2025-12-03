import uuid
import re
from aiogram import Router, F, Bot, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State, default_state
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
import logging
from typing import List, Dict, Any, Union

from config import settings
import database as db
import s3_storage
from data_cleaner import normalize_phone_number, normalize_phone_list # Переконайтесь, що цей імпорт коректний

# Ми імпортуємо MENU_KEYBOARD з main.py, але для коректної роботи в цьому файлі
# його потрібно або передавати, або визначити тут. Для простоти визначимо тут:
MENU_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Новий клієнт"), KeyboardButton(text="🔍 Пошук клієнта")],
        [KeyboardButton(text="❌ Скасувати")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Клавіатура для кроку з фото
PHOTO_SKIP_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Пропустити фото ⏭️")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

router = Router()
logging.basicConfig(level=logging.INFO)

# --- FSM СТАНИ (ОНОВЛЕНО) ---
class ClientForm(StatesGroup):
    # Додавання
    photo_or_skip = State()         # Крок 1: Фото або пропуск
    phone_and_comment = State()     # Крок 2: Номер та коментар

    # Пошук
    waiting_for_search_query = State()
    
    # Редагування
    waiting_for_edit_select = State()
    waiting_for_new_phone = State()
    waiting_for_new_comment = State()
    waiting_for_new_photo = State()
    
    # Для збереження даних знайденого клієнта
    found_client_data = State() 

# --- УТИЛІТИ ---

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
        f"**КЛІЄНТ ЗНАЙДЕНИЙ (ID: {client['id']})**\n"
        f"📞 Номери: {phones}\n"
        f"📝 Коментар: {client['comment']}\n"
        f"🔗 Кількість фото: {len(client['photo_url']) if client['photo_url'] else 0}"
    )

# --- 1. ЛОГІКА ДОДАВАННЯ (ОНОВЛЕНО) ---

@router.message(F.text == "➕ Новий клієнт", StateFilter(default_state))
async def cmd_add_client_start(message: Message, state: FSMContext):
    """Початок процесу додавання клієнта."""
    await message.answer(
        "**Крок 1/2:** Надішліть фото клієнта або натисніть 'Пропустити фото ⏭️'.",
        reply_markup=PHOTO_SKIP_KEYBOARD,
        parse_mode="Markdown"
    )
    await state.clear()
    await state.set_state(ClientForm.photo_or_skip)


@router.message(ClientForm.photo_or_skip, F.photo)
async def process_photo(message: Message, state: FSMContext, bot: Bot):
    """Обробка отриманого фото (Крок 1/2)."""
    
    # Завантаження фото
    photo_file = await bot.get_file(message.photo[-1].file_id)
    file_io = await bot.download_file(photo_file.file_path)
    
    filename = f"{message.from_user.id}_{uuid.uuid4()}.jpg"
    photo_url = await s3_storage.upload_photo_to_spaces(file_io, filename)
    
    if not photo_url:
        await message.answer("❌ Не вдалося завантажити фотографію. Спробуйте ще раз.")
        return

    await state.update_data(
        photo_url=[photo_url],
        telegram_id=message.from_user.id 
    )
    
    await message.answer(
        "**Крок 2/2:** Фото отримано. Тепер введіть номер(и) телефону та коментар в одному повідомленні. \n"
        "Наприклад: `+380501234567, другий номер: 0987654321, VIP клієнт, любить каву`",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(ClientForm.phone_and_comment)

@router.message(ClientForm.photo_or_skip, F.text == "Пропустити фото ⏭️")
async def skip_photo(message: Message, state: FSMContext):
    """Пропуск кроку з фото (Крок 1/2)."""
    await state.update_data(
        photo_url=[], # Пустий список
        telegram_id=message.from_user.id
    )
    
    await message.answer(
        "**Крок 2/2:** Додавання фото пропущено. Введіть номер(и) телефону та коментар в одному повідомленні. \n"
        "Наприклад: `+380501234567, другий номер: 0987654321, VIP клієнт, любить каву`",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.set_state(ClientForm.phone_and_comment)

@router.message(ClientForm.photo_or_skip)
async def process_photo_invalid(message: Message):
    await message.answer("Будь ласка, надішліть фото, або натисніть 'Пропустити фото ⏭️'.")


@router.message(ClientForm.phone_and_comment)
async def process_phone_and_comment(message: Message, state: FSMContext):
    """Обробка об'єднаного вводу: Номер(и) та Коментар (Крок 2/2)."""
    text = message.text
    
    # 1. Екстракція та нормалізація номерів телефону
    # Регулярний вираз для пошуку номерів: +?, цифри, пробіли, -, (), мінімум 5 символів
    phone_pattern = re.compile(r'\+?\s*[\d\s\-()]{5,}')
    raw_phones = phone_pattern.findall(text)
    
    normalized_phones = normalize_phone_list(raw_phones) 
    
    if not normalized_phones:
        await message.answer("❌ Не вдалося розпізнати жодного номера телефону. Будь ласка, спробуйте ще раз.")
        return
        
    # 2. Виділення коментаря
    comment_text = text
    
    # Видаляємо знайдені номери з тексту, щоб отримати чистий коментар
    for raw_phone in raw_phones:
        comment_text = comment_text.replace(raw_phone, '', 1) 
    
    # Очистка коментаря
    comment = re.sub(r'^\s*,\s*|\s*,\s*$', '', comment_text).strip()
    
    if not comment:
        comment = "(Коментар відсутній)"
    
    # 3. Збереження до БД
    data = await state.get_data()
    
    phone_str = ", ".join(normalized_phones)
    photo_urls = data.get('photo_url', [])
    photo_status = 'Є' if photo_urls else 'Немає'
    
    await db.add_client(
        telegram_id=data.get('telegram_id'), 
        phone=normalized_phones, 
        comment=comment, 
        face_encoding_array=[], 
        photo_url=photo_urls 
    )
    
    # 4. Завершення
    await state.clear()
    
    await message.answer(
        f"✅ **Клієнта успішно додано!**\n\n"
        f"**Номери:** {phone_str}\n"
        f"**Коментар:** {comment}\n"
        f"**Фото:** {photo_status}",
        reply_markup=MENU_KEYBOARD,
        parse_mode="Markdown"
    )

# --- 2. ЛОГІКА ПОШУКУ ---

@router.message(F.text == "🔍 Пошук клієнта", StateFilter(default_state))
@router.message(Command("search_client"), StateFilter(default_state))
async def start_search(message: Message, state: FSMContext):
    """Початок пошуку: просимо лише текст."""
    await state.clear()
    await message.answer(
        "Надішліть **текст** (номер, його частину або ключове слово з коментаря) для пошуку клієнта.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ClientForm.waiting_for_search_query)


@router.message(ClientForm.waiting_for_search_query, F.text)
async def process_search_query(message: Message, state: FSMContext):
    """Пошук клієнта за текстовим запитом."""
    query = message.text.strip()
    
    if len(query) < 3:
        await message.answer("Будь ласка, введіть принаймні 3 символи для пошуку.")
        return
    
    found_clients = await db.find_client_by_query(query)
    
    if not found_clients:
        await message.answer("❌ За вашим запитом клієнтів не знайдено.")
        await state.clear()
        return

    if len(found_clients) > 1:
        response = f"✅ Знайдено {len(found_clients)} клієнтів:\n\n"
        for i, client in enumerate(found_clients[:5]): 
            phones = ", ".join(client['phone']) if client['phone'] else "Не вказано"
            response += f"**{i+1}. ID:{client['id']}**: 📞{phones}, 📝{client['comment'][:20]}...\n"
        response += "\nБудь ласка, уточніть запит."
        await message.answer(response, parse_mode="Markdown")
        await state.clear()
    
    else:
        client = found_clients[0]
        await state.update_data(found_client_data=client)
        
        await message.answer(
            "✅ Знайдено єдиного клієнта. Що далі?",
            reply_markup=create_edit_inline_keyboard(client['id'])
        )
        await message.answer(format_client_info(client), parse_mode="Markdown")
        await state.set_state(ClientForm.waiting_for_edit_select)
    
# --- 3. ЛОГІКА РЕДАГУВАННЯ ---

# 3.1. Додати номер
@router.callback_query(F.data.startswith("edit_phone_"))
async def start_add_phone(call: CallbackQuery, state: FSMContext):
    db_id = int(call.data.split('_')[-1])
    await state.update_data(client_id_to_edit=db_id)
    await call.message.edit_text("Введіть **новий номер** телефону (буде доданий до існуючих):")
    await state.set_state(ClientForm.waiting_for_new_phone)
    await call.answer()

@router.message(ClientForm.waiting_for_new_phone)
async def process_new_phone(message: Message, state: FSMContext):
    raw_phone = message.text
    new_phone = normalize_phone_number(raw_phone)
    
    if not new_phone or (len(new_phone.strip('+')) < 6):
        await message.answer("Некоректний формат номера. Введіть його ще раз.")
        return

    data = await state.get_data()
    db_id = data.get('client_id_to_edit')
    
    client = await db.find_client_by_id(db_id)
    if not client:
        await message.answer("❌ Клієнта не знайдено.")
        await state.clear()
        return

    updated_phones = client['phone']
    if new_phone not in updated_phones:
        updated_phones.append(new_phone)
    
    await db.update_client_data(db_id, updated_phones, client['comment'], client['photo_url'])
    
    await message.answer(f"✅ Номер **{new_phone}** успішно додано до клієнта ID:{db_id}.", reply_markup=MENU_KEYBOARD)
    await state.clear()


# 3.2. Змінити коментар
@router.callback_query(F.data.startswith("edit_comment_"))
async def start_edit_comment(call: CallbackQuery, state: FSMContext):
    db_id = int(call.data.split('_')[-1])
    await state.update_data(client_id_to_edit=db_id)
    await call.message.edit_text("Введіть **новий коментар/примітки** для клієнта:")
    await state.set_state(ClientForm.waiting_for_new_comment)
    await call.answer()

@router.message(ClientForm.waiting_for_new_comment)
async def process_new_comment(message: Message, state: FSMContext):
    new_comment = message.text.strip()
    data = await state.get_data()
    db_id = data.get('client_id_to_edit')
    
    client = await db.find_client_by_id(db_id)
    if not client:
        await message.answer("❌ Клієнта не знайдено.")
        await state.clear()
        return

    await db.update_client_data(
        db_id, client['phone'], new_comment, client['photo_url']
    )
    
    await message.answer(f"✅ Коментар для клієнта ID:{db_id} успішно оновлено.", reply_markup=MENU_KEYBOARD)
    await state.clear()

# 3.3. Додати фото
@router.callback_query(F.data.startswith("edit_photo_"))
async def start_add_photo(call: CallbackQuery, state: FSMContext):
    db_id = int(call.data.split('_')[-1])
    await state.update_data(client_id_to_edit=db_id)
    await call.message.edit_text("Надішліть **нову фотографію обличчя** для додавання до профілю клієнта.")
    await state.set_state(ClientForm.waiting_for_new_photo)
    await call.answer()

@router.message(ClientForm.waiting_for_new_photo, F.photo)
async def process_new_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    db_id = data.get('client_id_to_edit')
    
    # Завантаження фото
    photo_file = await bot.get_file(message.photo[-1].file_id)
    file_io = await bot.download_file(photo_file.file_path)
    
    filename = f"{db_id}_{uuid.uuid4()}.jpg"
    new_photo_url = await s3_storage.upload_photo_to_spaces(file_io, filename)
    
    if not new_photo_url:
        await message.answer("❌ Не вдалося завантажити фотографію. Спробуйте ще раз.")
        await state.clear()
        return
    
    client = await db.find_client_by_id(db_id)
    if not client:
        await message.answer("❌ Клієнта не знайдено.")
        await state.clear()
        return

    updated_photos = client['photo_url']
    updated_photos.append(new_photo_url)
    
    # Оновлення даних
    await db.update_client_data(
        db_id, client['phone'], client['comment'], updated_photos
    )
    
    await message.answer(f"✅ Нова фотографія успішно додана до профілю клієнта ID:{db_id}.", reply_markup=MENU_KEYBOARD)
    await state.clear()
    
# 3.4. Видалити клієнта
@router.callback_query(F.data.startswith("delete_client_"))
async def confirm_delete_client(call: CallbackQuery, state: FSMContext):
    db_id = int(call.data.split('_')[-1])
    
    was_deleted = await db.delete_client(db_id)

    if was_deleted:
        await call.message.edit_text(f"❌ Клієнта ID:{db_id} **успішно видалено** з бази даних.", parse_mode="Markdown")
    else:
        await call.message.edit_text(f"⚠️ Помилка: Клієнт ID:{db_id} не знайдений або не був видалений.")
        
    await state.clear()
    await call.answer()
