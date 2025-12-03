# Використовуємо офіційний образ Python 3.9
FROM python:3.9

# Встановлюємо системні залежності ОДНИМ ШАРОМ
# libpq-dev: потрібен для компіляції асинхронного драйвера PostgreSQL (asyncpg)
# build-essential: базові утиліти для компіляції C-розширень
RUN apt-get update && apt-get install -y \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо файл залежностей та встановлюємо Python-бібліотеки
COPY requirements.txt .
# УВАГА: requirements.txt не повинен містити dlib, face_recognition, numpy!
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь решту коду в контейнер
COPY . .

# Команда запуску застосунку
# Запускаємо main.py
CMD ["python", "main.py"]
