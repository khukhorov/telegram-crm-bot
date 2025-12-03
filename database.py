import asyncpg
from config import settings
import json
import logging
from typing import List

db_pool = None
logging.basicConfig(level=logging.INFO)

async def init_db():
    """Створює пул підключень до PostgreSQL та ініціалізує таблиці."""
    global db_pool
    if db_pool:
        return

    try:
        db_pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)
        
        async with db_pool.acquire() as connection:
            # Використовуємо JSONB для зберігання списку номерів та URL-адрес
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
    """Зберігає або оновлює дані клієнта (приймає списки)."""
    if not db_pool:
        raise Exception("Database pool is not initialized.")
        
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

async def get_all_encodings():
    """Отримує всі енкодинги з БД для пошуку по фото."""
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
    if not db_pool:
        raise Exception("Database pool is not initialized.")
    async with db_pool.acquire() as connection:
        record = await connection.fetchrow("SELECT * FROM clients WHERE id = $1", db_id)
        if record:
            return {**dict(record), 'phone': json.loads(record['phone']), 'photo_url': json.loads(record['photo_url'])}
        return None

# Функція для оновлення даних
async def update_client_data(db_id: int, phone: List[str], comment: str, photo_url: List[str]):
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
