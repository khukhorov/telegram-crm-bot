# Використовуємо повний Python-образ (не -slim!)
FROM python:3.9

# Встановлюємо системні залежності 
RUN apt-get update && apt-get install -y \
    cmake \
    libsm6 \
    libxrender1 \
    libfontconfig1 \
    libxext6 \
    build-essential \
    pkg-config \
    libpq-dev \  # <<< ДЛЯ asyncpg
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копіюємо список залежностей та встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проєкту
COPY . .

# Команда запуску
CMD ["python", "main.py"]
