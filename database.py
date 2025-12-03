import asyncpg
from config import settings
import json
import logging
import re
from typing import List, Dict, Any, Union

# ІМПОРТУЄМО ФУНКЦІЮ НОРМАЛІЗАЦІЇ З ВАШОГО ОКРЕМОГО ФАЙЛУ
from data_cleaner import normalize_phone_number 

db_pool = None
logging.basicConfig(level=logging.INFO)

# --- УТИЛІТА: (Попередня функція нормалізації ВИДАЛЕНА) ---

async def init_db():
    """Створює пул підключень до PostgreSQL та ініціалізує таблиці."""
    global db_pool
    if db_pool:
        return

    try:
        db_pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)
        async with db_pool.acquire() as connection:
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
    """Зберігає або оновлює дані клієнта (номери мають бути нормалізовані)."""
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


async def find_client_by_query(query: str) -> List[Dict[str, Any]]:
    """Пошук клієнта за номером (повним/частиною) або ключовими словами у коментарі."""
    if not db_pool:
        raise Exception("Database pool is not initialized.")

    # ВИКОРИСТАННЯ ЗОВНІШНЬОЇ ФУНКЦІЇ НОРМАЛІЗАЦІЇ
    search_term = normalize_phone_number(query)
    
    comment_param = f"%{query}%"
    phone_param = f"%{search_term}%" 
    last_5_digits = f"%{search_term[-5:]}" if len(search_term) >= 5 else phone_param

    sql_query = """
        SELECT * FROM clients 
        WHERE 
            comment ILIKE $1 
        OR 
            EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(phone) AS elem
                WHERE 
                    elem ILIKE $2 OR      
                    elem ILIKE $3         
            )
    """

    async with db_pool.acquire() as connection:
        records = await connection.fetch(sql_query, comment_param, phone_param, last_5_digits)
        
        results = []
        for record in records:
            results.append({
                **dict(record), 
                'phone': json.loads(record['phone']), 
                'photo_url': json.loads(record['photo_url'])
            })
        return results

async def find_client_by_id(db_id: int):
    """Пошук клієнта за внутрішнім ID."""
    if not db_pool:
        raise Exception("Database pool is not initialized.")
    async with db_pool.acquire() as connection:
        record = await connection.fetchrow("SELECT * FROM clients WHERE id = $1", db_id)
        if record:
            return {**dict(record), 'phone': json.loads(record['phone']), 'photo_url': json.loads(record['photo_url'])}
        return None

async def update_client_data(db_id: int, phone: List[str], comment: str, photo_url: List[str]):
    """Оновлення даних клієнта."""
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

async def delete_client(db_id: int) -> bool:
    """Видаляє клієнта за внутрішнім ID."""
    if not db_pool:
        raise Exception("Database pool is not initialized.")
    async with db_pool.acquire() as connection:
        result = await connection.execute("DELETE FROM clients WHERE id = $1", db_id)
        return result == 'DELETE 1'
        
async def get_all_encodings():
    """Залишено як заглушка."""
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
