import boto3
import os
from config import settings
from io import BytesIO
import logging

logging.basicConfig(level=logging.INFO)

# Ініціалізація клієнта S3 для DigitalOcean Spaces
s3_client = boto3.client(
    's3',
    endpoint_url=settings.SPACES_ENDPOINT_URL,
    aws_access_key_id=settings.SPACES_ACCESS_KEY,
    aws_secret_access_key=settings.SPACES_SECRET_KEY
)

async def upload_photo_to_spaces(file_data: BytesIO, filename: str) -> str:
    """Завантажує файл на DigitalOcean Spaces та повертає його URL."""
    try:
        s3_client.upload_fileobj(
            file_data,
            settings.SPACES_BUCKET_NAME,
            filename,
            # Дозволяємо публічний доступ до файлу (щоб Telegram міг його відобразити)
            ExtraArgs={'ACL': 'public-read', 'ContentType': 'image/jpeg'} 
        )
        # Формуємо публічну URL-адресу для зберігання у PostgreSQL
        url = f"{settings.SPACES_ENDPOINT_URL}/{settings.SPACES_BUCKET_NAME}/{filename}"
        logging.info(f"Photo uploaded to Spaces: {url}")
        return url
        
    except Exception as e:
        logging.error(f"Error uploading to Spaces: {e}")
        return None

# Функція для отримання фотографії (якщо потрібно буде завантажити її назад)
async def get_photo_from_spaces(filename: str) -> BytesIO:
    """Отримує файл з Spaces."""
    try:
        file_buffer = BytesIO()
        s3_client.download_fileobj(
            settings.SPACES_BUCKET_NAME,
            filename,
            file_buffer
        )
        file_buffer.seek(0)
        return file_buffer
    except Exception as e:
        logging.error(f"Error downloading from Spaces: {e}")
        return None
