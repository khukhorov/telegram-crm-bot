import asyncpg
from config import settings
import json
import logging
import re # Додано для нормалізації номера всередині пошуку
from typing import List, Dict, Any

db_pool = None
logging.basicConfig(level=logging.INFO)

# --- УТИЛІТА: Нормалізація номера телефону ---
# Ця функція використовується всередині find_client_by_query
def _normalize_phone_number(raw_number: str) -> str:
    """Видаляє всі символи, крім цифр та знака '+', залишаючи '+' на початку."""
    # Видаляємо всі символи, крім цифр та знака '+'
    cleaned_number = re.sub(r'[^0-9\+]', '', raw_number)
    
    # Якщо випадково ввели багато '+', залишаємо лише один
    if cleaned_number.startswith('++'):
        cleaned_number = '+' + cleaned_number.lstrip('+')
        
    return cleaned_number
# ---------------------------------------------


async def init_db():
    """Створює пул підключень до PostgreSQL та ініціалізує таблиці."""
    global db_pool
    if db_pool:
        return

    try:
        # Пул підключень
        db_pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)
        
        async with db_pool.acquire() as connection:
            # Створення таблиці clients
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    phone JSONB, 
                    comment TEXT,
                    face_encoding JSONB, 
                    photo_url JSONB
                );
            """)
        logging.info("INFO: PostgreSQL database and tables initialized successfully.")

    except Exception as e:
        logging.error(f"ERROR: Failed to connect or initialize PostgreSQL: {e}")
        raise

async def add_client(telegram_id: int, phone: List[str], comment: str, face_encoding_array: List[float], photo_url: List[str]):
    """
    Зберігає або оновлює дані клієнта. 
    Примітка: Номери телефону в 'phone' мають бути вже нормалізовані
    перед викликом цієї функції.
    """
    if not db_pool:
        raise Exception("Database pool is not initialized.")
        
    # Конвертація списків у JSONB
    encoding_json = json.dumps(face_encoding_array)
    phone_json = json.dumps(phone)
    photo_json = json.dumps(photo_url)
    
    async with db_pool.acquire() as connection:
        await connection.execute("""
            INSERT INTO clients (telegram_id, phone, comment, face_encoding, photo_url) 
            VALUES ($1, $2, $3, $4, $5) 
            ON CONFLICT (telegram_id) 
            DO UPDATE SET 
                phone = $2, 
                comment = $3,
                face_encoding = $4,
                photo_url = $5;
        """, telegram_id, phone_json, comment, encoding_json, photo_json)

# -------------------------------------------------------------------------
# НОВА ФУНКЦІЯ: ПОШУК З УРАХУВАННЯМ JSONB ТА ЧАСТИН НОМЕРА
# -------------------------------------------------------------------------
async def find_client_by_query(query: str) -> List[Dict[str, Any]]:
    """
    Пошук клієнта за:
    1. Ключовими словами у коментарі (регістронезалежно).
    2. Повним або частиною нормалізованого номера.
    3. Останніми 5 цифрами номера.
    """
    if not db_pool:
        raise Exception("Database pool is not initialized.")

    # Нормалізація запиту для пошуку номерів: видаляємо всі, крім цифр та '+'
    search_term = _normalize_phone_number(query)
    
    # Визначаємо параметри для SQL-запиту
    comment_param = f"%{query}%" # Для ILIKE у коментарі
    phone_param = f"%{search_term}%" # Для пошуку частини нормалізованого номера
    
    # Обрізаємо пошуковий термін до останніх 5 символів для пошуку кінця номера
    last_5_digits = f"%{search_term[-5:]}" if len(search_term) >= 5 else phone_param

    sql_query = """
        SELECT * FROM clients 
        WHERE 
            -- 1. Пошук за коментарем (регістронезалежний, містить будь-де)
            comment ILIKE $1 
        OR 
            -- 2. Пошук у масиві телефонів (використовуємо jsonb_array_elements_text)
            EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(phone) AS elem
                WHERE 
                    -- Елемент містить:
                    elem ILIKE $2 OR      -- повний/нормалізований номер або його частину
                    elem ILIKE $3         -- останні 5 цифр
            )
    """

    async with db_pool.acquire() as connection:
        records = await connection.fetch(sql_query, comment_param, phone_param, last_5_digits)
        
        results = []
        for record in records:
            # Розпаковуємо JSONB поля для Python
            results.append({
                **dict(record), 
                'phone': json.loads(record['phone']), 
                'photo_url': json.loads(record['photo_url'])
            })
        return results

# -------------------------------------------------------------------------


async def get_all_encodings():
    """Отримує всі енкодинги з БД для пошуку по фото."""
    # (Ця функція залишилася без змін)
    if not db_pool:
        raise Exception("Database pool is not initialized.")

    async with db_pool.acquire() as connection:
        records = await connection.fetch("SELECT id, telegram_id, phone, comment, face_encoding, photo_url FROM clients")
        
        encodings = []
        for record in records:
            encodings.append({
                'db_id': record['id'],
                'telegram_id': record['telegram_id'],
                'phone': json.loads(record['phone']),
                'comment': record['comment'],
                'photo_url': json.loads(record['photo_url']),
                'encoding': json.loads(record['face_encoding'])
            })
        return encodings

async def find_client_by_id(db_id: int):
    """Пошук клієнта за внутрішнім ID."""
    # (Ця функція залишилася без змін)
    if not db_pool:
        raise Exception("Database pool is not initialized.")
    async with db_pool.acquire() as connection:
        record = await connection.fetchrow("SELECT * FROM clients WHERE id = $1", db_id)
        if record:
            return {**dict(record), 'phone': json.loads(record['phone']), 'photo_url': json.loads(record['photo_url'])}
        return None

async def update_client_data(db_id: int, phone: List[str], comment: str, photo_url: List[str]):
    """
    Оновлення даних клієнта. 
    Примітка: Номери телефону в 'phone' мають бути вже нормалізовані
    перед викликом цієї функції.
    """
    # (Ця функція залишилася без змін, крім docstring)
    if not db_pool:
        raise Exception("Database pool is not initialized.")
    
    phone_json = json.dumps(phone)
    photo_json = json.dumps(photo_url)
    
    async with db_pool.acquire() as connection:
        await connection.execute("""
            UPDATE clients 
            SET phone = $2, comment = $3, photo_url = $4 
            WHERE id = $1;
        """, db_id, phone_json, comment, photo_json)
