import os
from dotenv import load_dotenv

# Завантажуємо змінні з .env, якщо працюємо локально
load_dotenv()

class Settings:
    # 1. Основний токен бота
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")

    # 2. Ключі для надійного завантаження фото (потрібно отримати на my.telegram.org)
    API_ID: str = os.getenv("API_ID")
    API_HASH: str = os.getenv("API_HASH")

    # 3. АДРЕСА ПОСТІЙНОЇ БД PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # 4. Тимчасові змінні для сервісу Spaces (будемо додавати на наступному кроці)
    SPACES_ACCESS_KEY: str = os.getenv("SPACES_ACCESS_KEY")
    SPACES_SECRET_KEY: str = os.getenv("SPACES_SECRET_KEY")
    SPACES_ENDPOINT_URL: str = os.getenv("SPACES_ENDPOINT_URL")

settings = Settings()

# Перевірка критичних змінних
if not settings.BOT_TOKEN:
    raise ValueError("BOT_TOKEN не знайдено.")

if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL для PostgreSQL не знайдено. Підключення БД неможливе.")
