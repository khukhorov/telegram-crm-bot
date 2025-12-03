FROM python:3.9

# Вся інструкція RUN має бути єдиним блоком
RUN apt-get update && apt-get install -y \
    cmake \
    libsm6 \
    libxrender1 \
    libfontconfig1 \
    libxext6 \
    build-essential \
    pkg-config \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
