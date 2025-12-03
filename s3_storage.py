import boto3
from config import settings
from io import BytesIO
import logging
import os

logging.basicConfig(level=logging.INFO)

# Ініціалізація клієнта S3 для DigitalOcean Spaces
s3_client = boto3.client(
    's3',
    endpoint_url=settings.SPACES_ENDPOINT_URL,
    aws_access_key_id=settings.SPACES_ACCESS_KEY,
    aws_secret_access_key=settings.SPACES_SECRET_KEY
)

def get_photo_url(filename: str) -> str:
    """Формує публічну URL-адресу файлу."""
    endpoint = settings.SPACES_ENDPOINT_URL.rstrip('/')
    return f"{endpoint}/{settings.SPACES_BUCKET_NAME}/{filename}"


async def upload_photo_to_spaces(file_data: BytesIO, filename: str) -> str:
    """Завантажує файл на DigitalOcean Spaces та повертає його URL."""
    try:
        file_data.seek(0)
        s3_client.upload_fileobj(
            file_data,
            settings.SPACES_BUCKET_NAME,
            filename,
            ExtraArgs={'ACL': 'public-read', 'ContentType': 'image/jpeg'} 
        )
        return get_photo_url(filename)
        
    except Exception as e:
        logging.error(f"Error uploading to Spaces: {e}")
        return None
