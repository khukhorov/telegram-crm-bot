import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Telegram Keys
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    API_ID: str = os.getenv("API_ID")
    API_HASH: str = os.getenv("API_HASH")

    # PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # DigitalOcean Spaces
    SPACES_ACCESS_KEY: str = os.getenv("SPACES_ACCESS_KEY")
    SPACES_SECRET_KEY: str = os.getenv("SPACES_SECRET_KEY")
    SPACES_ENDPOINT_URL: str = os.getenv("SPACES_ENDPOINT_URL")
    SPACES_BUCKET_NAME: str = os.getenv("SPACES_BUCKET_NAME")

settings = Settings()

# Критична перевірка: без токена, БД та API-ключів бот не працюватиме
if not all([settings.BOT_TOKEN, settings.DATABASE_URL, settings.API_ID, settings.API_HASH]):
    raise ValueError("Критична помилка: Не всі необхідні ключі (BOT_TOKEN, DATABASE_URL, API_ID, API_HASH) знайдені у змінних середовища.")
