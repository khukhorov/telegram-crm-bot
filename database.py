import asyncpg
from config import settings
import json
import logging

db_pool = None
logging.basicConfig(level=logging.INFO)

async def init_db():
    """Створює пул підключень до PostgreSQL та ініціалізує таблиці."""
    global db_pool
    if db_pool:
        return

    try:
        # Створення пулу підключень
        db_pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)
        
        # Ініціалізація таблиці clients
        async with db_pool.acquire() as connection:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    fullname VARCHAR(255),
                    phone VARCHAR(20),
                    face_encoding JSONB, 
                    photo_url VARCHAR(512)
                );
            """)
        logging.info("PostgreSQL database and tables initialized successfully.")

    except Exception as e:
        logging.error(f"Failed to connect or initialize PostgreSQL: {e}")
        raise

# --- ПРИКЛАД ФУНКЦІЇ ---
async def add_client(telegram_id: int, fullname: str, phone: str, face_encoding_array: list, photo_url: str = None):
    """Зберігає нового клієнта в PostgreSQL."""
    if not db_pool:
        raise Exception("Database pool is not initialized.")
        
    encoding_json = json.dumps(face_encoding_array)
    
    async with db_pool.acquire() as connection:
        await connection.execute("""
            INSERT INTO clients (telegram_id, fullname, phone, face_encoding, photo_url) 
            VALUES ($1, $2, $3, $4, $5) 
            ON CONFLICT (telegram_id) 
            DO UPDATE SET 
                fullname = $2, 
                phone = $3,
                face_encoding = $4,
                photo_url = $5;
        """, telegram_id, fullname, phone, encoding_json, photo_url)
