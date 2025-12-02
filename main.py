import asyncio
import os
import logging
import face_recognition
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                           InlineKeyboardMarkup, InlineKeyboardButton)

import database as db

# Отримуємо токен з environment
TOKEN = os.getenv("BOT_TOKEN")

# Налаштування логування
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- МАШИНА СТАНІВ (FSM) ---
class AddClientState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_note_photo = State()

class EditClientState(StatesGroup):
    waiting_for_new_phone = State()
    waiting_for_new_photo = State()
    waiting_for_new_note = State()


# --- КОНСТАНТИ ТА УТИЛІТИ (мономовна версія) ---
TEXTS = {
    'start_msg': "База клієнтів готова до роботи.",
    'add_btn': "➕ Додати клієнта",
    'search_btn': "🔍 Пошук",
    'step1': "Крок 1/2: Введіть номер телефону:",
    'step2': "Крок 2/2: Надішліть нотатку.\nМожна прикріпити ФОТО (щоб розпізнавати обличчя).",
    'saving': "⏳ Зберігаю...",
    'saved': "✅ Клієнт збережений!",
    'search_prompt': "Надішліть **Текст** (номер/ім'я) або **Фото** обличчя.",
    'not_found': "Нічого не знайдено.",
    'photo_scanning': "⏳ Сканую базу за обличчям...",
    'face_not_found': "⚠️ Обличчя на фото не знайдено.",
    'match_not_found': "Збігів не знайдено.",
    'note_untranslated': "Без нотатки",
    'phone_add_prompt': "Введіть додатковий номер телефону:",
    'photo_add_prompt': "Надішліть нове фото клієнта:",
    'note_change_prompt': "Введіть новий текст нотатки:",
    'phone_added': "Номер додано!",
    'photo_added': "Фото та зліпок обличчя додано!",
    'note_updated': "Нотатку оновлено!",
    'face_not_found_small': "Обличчя не знайдено, спробуйте інше фото.",
    'client_deleted': "Клієнта ID {client_id} видалено.",
    'search_error': "⚠️ **Помилка пошуку!** Спробуйте ще раз.",
    'conflict_phone': "❌ **КОНФЛІКТ: Телефон {phone} вже існує!**\nКлієнт ID {client_id} вже в базі.",
}

def get_text(key):
    # У цій версії просто повертаємо текст українською
    return TEXTS.get(key, TEXTS['start_msg'])

def format_phone_display(phone_number):
    """Форматує номер телефону для кращого відображення."""
    if not phone_number:
        return ""
    
    # Видаляємо '+' для логіки форматування, якщо він є
    prefix = ""
    if phone_number.startswith('+'):
        prefix = '+'
        digits = phone_number[1:]
    else:
        digits = phone_number
    
    # Намагаємося застосувати загальноприйнятий український формат
    if len(digits) == 12 and digits.startswith('380'): # +380 XX XXX XX XX
        return f"{prefix}{digits[:3]} ({digits[3:5]}) {digits[5:8]} {digits[8:10]} {digits[10:]}"
    elif len(digits) == 10 and digits.startswith('0'): # 0 XX XXX XX XX
        return f"{prefix}({digits[:3]}) {digits[3:6]} {digits[6:8]} {digits[8:]}"
    # Якщо формат невідомий або короткий, повертаємо його звичайним
    return phone_number 

# --- КЛАВІАТУРИ ---
def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXTS['add_btn']), KeyboardButton(text=TEXTS['search_btn'])],
        ],
        resize_keyboard=True
    )

def get_edit_kb(client_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Додати номер", callback_data=f"addph_{client_id}"),
         InlineKeyboardButton(text="📷 Додати фото", callback_data=f"addimg_{client_id}")],
        [InlineKeyboardButton(text="📝 Змінити нотатку", callback_data=f"chnote_{client_id}")],
        [InlineKeyboardButton(text="❌ Видалити клієнта", callback_data=f"del_{client_id}")]
    ])

# --- ДОПОМІЖНА ФУНКЦІЯ: ПОШУК ОБЛИЧЧЯ ---
async def find_face_match(target_encoding):
    all_faces = await db.get_all_face_encodings()
    
    for entry in all_faces:
        is_match = face_recognition.compare_faces([entry['encoding']], target_encoding, tolerance=0.6)
        if is_match[0]:
            return entry['client_id']
    
    return None

# --- СТАРТ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await db.init_db()
    
    start_msg = get_text('start_msg')
    main_kb = get_main_kb()
    
    await message.answer(start_msg, reply_markup=main_kb)

# ===========================
# 1. ЛОГІКА ДОДАВАННЯ (Create)
# ===========================
@dp.message(F.text.regexp(r".*Додати клієнта.*"))
async def start_add(message: types.Message, state: FSMContext):
    step1_msg = get_text('step1')
    await message.answer(step1_msg, reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddClientState.waiting_for_phone)

@dp.message(AddClientState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    step2_msg = get_text('step2')
    await message.answer(step2_msg)
    await state.set_state(AddClientState.waiting_for_note_photo)

@dp.message(AddClientState.waiting_for_note_photo)
async def process_note_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    phone = data['phone']
    
    # 1. ПЕРЕВІРКА НА КОНФЛІКТ ТЕЛЕФОНУ
    existing_client_id = await db.get_client_id_by_phone(phone)
    if existing_client_id:
        # Конфлікт знайдено!
        edit_kb = get_edit_kb(existing_client_id) 
        conflict_msg = get_text('conflict_phone')
        
        await message.answer(
            conflict_msg.format(phone=phone, client_id=existing_client_id),
            reply_markup=edit_kb
        )
        await state.clear()
        return
    
    # 2. ПІДГОТОВКА НОТАТКИ
    note = message.caption if message.caption else message.text
    if not note: note = get_text('note_untranslated') 
    
    face_encoding = None
    photo_file_id = None
    
    msg_wait_text = get_text('saving')
    msg_wait = await message.answer(msg_wait_text)
    
    # 3. Обробка ФОТО
    if message.photo:
        photo_file_id = message.photo[-1].file_id 
        photo_file = await bot.download(message.photo[-1])
        image = face_recognition.load_image_file(photo_file)
        encodings = face_recognition.face_encodings(image)
        
        if encodings:
            face_encoding = encodings[0]

    # 4. ДОДАВАННЯ НОВОГО КЛІЄНТА
    await db.create_client(phone, note, face_encoding, photo_file_id)
    
    saved_msg = get_text('saved')
    main_kb = get_main_kb()

    await msg_wait.delete()
    await message.answer(saved_msg, reply_markup=main_kb)
    await state.clear()

# ===========================
# 2. ЛОГІКА РЕДАГУВАННЯ (Edit) 
# ===========================

# --- Додати телефон ---
@dp.callback_query(F.data.startswith("addph_"))
async def cb_add_phone(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[1])
    await state.update_data(client_id=cid)
    prompt = get_text('phone_add_prompt')
    await callback.message.answer(prompt)
    await state.set_state(EditClientState.waiting_for_new_phone)
    await callback.answer()

@dp.message(EditClientState.waiting_for_new_phone)
async def process_new_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # Додавання номера тут також використовує нормалізацію з database.py
    await db.add_phone(data['client_id'], message.text)
    main_kb = get_main_kb()
    response = get_text('phone_added')
    await message.answer(response, reply_markup=main_kb)
    await state.clear()

# --- Додати фото ---
@dp.callback_query(F.data.startswith("addimg_"))
async def cb_add_img(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[1])
    await state.update_data(client_id=cid)
    prompt = get_text('photo_add_prompt')
    await callback.message.answer(prompt)
    await state.set_state(EditClientState.waiting_for_new_photo)
    await callback.answer()

@dp.message(EditClientState.waiting_for_new_photo, F.photo)
async def process_new_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    photo_file_id = message.photo[-1].file_id
    photo_file = await bot.download(message.photo[-1])
    image = face_recognition.load_image_file(photo_file)
    encodings = face_recognition.face_encodings(image)
    
    if encodings:
        await db.add_face(data['client_id'], encodings[0], photo_file_id)
        main_kb = get_main_kb()
        response = get_text('photo_added')
        await message.answer(response, reply_markup=main_kb)
    else:
        response = get_text('face_not_found_small')
        await message.answer(response)
        return 
        
    await state.clear()

# --- Змінити нотатку ---
@dp.callback_query(F.data.startswith("chnote_"))
async def cb_change_note(callback: types.CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[1])
    await state.update_data(client_id=cid)
    prompt = get_text('note_change_prompt')
    await callback.message.answer(prompt)
    await state.set_state(EditClientState.waiting_for_new_note)
    await callback.answer()

@dp.message(EditClientState.waiting_for_new_note)
async def process_new_note(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Зберігаємо нотатку
    await db.update_note(data['client_id'], message.text)
    
    main_kb = get_main_kb()
    response = get_text('note_updated')
    await message.answer(response, reply_markup=main_kb)
    await state.clear()

# --- Видалити ---
@dp.callback_query(F.data.startswith("del_"))
async def cb_delete(callback: types.CallbackQuery):
    cid = int(callback.data.split("_")[1])
    await db.delete_client(cid)
    response = get_text('client_deleted')
    await callback.message.edit_text(response.format(client_id=cid))
    await callback.answer("Видалено")


# ===========================
# 3. ЛОГІКА ПОШУКУ (Search)
# ===========================
@dp.message(F.text.regexp(r".*Пошук.*"))
async def start_search(message: types.Message):
    search_prompt = get_text('search_prompt')
    await message.answer(search_prompt)

# Обробка текстового пошуку: ловить все, що не є кнопкою/фото/командою
@dp.message(F.text & ~F.text.in_({TEXTS['add_btn'], TEXTS['search_btn']}))
async def search_text(message: types.Message):
    try:
        client_ids = await db.search_by_text(message.text)
        if not client_ids:
            not_found_msg = get_text('not_found')
            await message.answer(not_found_msg)
            return
        await show_results(message, client_ids)
    except Exception as e:
        logging.error(f"Помилка текстового пошуку: {e}")
        error_msg = get_text('search_error')
        await message.answer(error_msg)


@dp.message(F.photo)
async def search_photo(message: types.Message):
    photo_scanning_msg = get_text('photo_scanning')
    wait_msg = await message.answer(photo_scanning_msg)
    
    try:
        photo_file = await bot.download(message.photo[-1])
        unknown_image = face_recognition.load_image_file(photo_file)
        unknown_encodings = face_recognition.face_encodings(unknown_image)
    
        if not unknown_encodings:
            face_not_found_msg = get_text('face_not_found')
            await wait_msg.edit_text(face_not_found_msg)
            return

        target_encoding = unknown_encodings[0]
        found_client_ids = set()
        
        client_id_match = await find_face_match(target_encoding)
        if client_id_match:
             found_client_ids.add(client_id_match)
        
        await wait_msg.delete()
        
        if not found_client_ids:
            match_not_found_msg = get_text('match_not_found')
            await message.answer(match_not_found_msg)
        else:
            await show_results(message, list(found_client_ids))
            
    except Exception as e:
        await wait_msg.delete()
        logging.error(f"Помилка фотопошуку: {e}")
        error_msg = get_text('search_error')
        await message.answer(error_msg)


async def show_results(message, client_ids):
    for cid in client_ids:
        info = await db.get_client_full_info(cid)
        if not info: continue
        
        # Форматуємо кожен номер для відображення
        formatted_phones = [format_phone_display(p) for p in info['phones']]
        phones_str = ", ".join(formatted_phones)
        
        text = (f"🆔 ID: {cid}\n"
                f"📞 Телефони: {phones_str}\n"
                f"📝 Нотатка: {info['note']}")
        
        kb = get_edit_kb(cid)
        
        if info['photo_file_id']:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=info['photo_file_id'],
                caption=text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        else:
            await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# --- ЗАПУСК ---
async def main():
    await db.init_db()
    logging.info(f"Start polling for bot @{await bot.get_me()}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())