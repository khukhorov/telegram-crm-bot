import aiosqlite
import pickle
import os

DB_PATH = "data/clients.db"

# --- УТИЛІТА ДЛЯ НОРМАЛІЗАЦІЇ НОМЕРА ---
def normalize_phone(phone_number):
    """Видаляє пробіли/дужки/дефіси, зберігаючи '+' на початку."""
    if not phone_number:
        return None
        
    # 1. Визначення префіксу '+'
    has_plus_prefix = phone_number.strip().startswith('+')
    
    # 2. Нормалізація: видалення усіх символів, окрім цифр
    normalized_digits = ''.join(filter(str.isdigit, phone_number))
    
    # 3. Формування нормалізованого номера для збереження
    if has_plus_prefix:
        return f"+{normalized_digits}"
    else:
        return normalized_digits

# --- ІНІЦІАЛІЗАЦІЯ ---
async def init_db():
    os.makedirs("data", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблиця 1: clients (основна інфо)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note TEXT
            )
        """)
        # Таблиця 2: phones
        await db.execute("""
            CREATE TABLE IF NOT EXISTS phones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                phone_number TEXT,
                FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
            )
        """)
        # Таблиця 3: faces
        await db.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                encoding BLOB,
                file_id TEXT,
                FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
            )
        """)
        await db.commit()

# --- СТВОРЕННЯ (Create) ---
async def create_client(phone, note, encoding=None, file_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO clients (note) VALUES (?)", (note,))
        client_id = cursor.lastrowid
        
        # Використовуємо нормалізацію
        normalized_phone = normalize_phone(phone)
        
        if normalized_phone:
            await db.execute("INSERT INTO phones (client_id, phone_number) VALUES (?, ?)", (client_id, normalized_phone))
        
        if encoding is not None:
            blob = pickle.dumps(encoding)
            await db.execute("INSERT INTO faces (client_id, encoding, file_id) VALUES (?, ?, ?)", (client_id, blob, file_id))
        
        await db.commit()
        return client_id

# --- РЕДАГУВАННЯ (Edit) ---
async def add_phone(client_id, phone):
    async with aiosqlite.connect(DB_PATH) as db:
        # Використовуємо нормалізацію при додаванні
        normalized_phone = normalize_phone(phone)
        if normalized_phone:
            await db.execute("INSERT INTO phones (client_id, phone_number) VALUES (?, ?)", (client_id, normalized_phone))
            await db.commit()

async def add_face(client_id, encoding, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        blob = pickle.dumps(encoding)
        await db.execute("INSERT INTO faces (client_id, encoding, file_id) VALUES (?, ?, ?)", (client_id, blob, file_id))
        await db.commit()

async def update_note(client_id, new_note):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE clients SET note = ? WHERE id = ?", (new_note, client_id))
        await db.commit()

async def delete_client(client_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM phones WHERE client_id = ?", (client_id,))
        await db.execute("DELETE FROM faces WHERE client_id = ?", (client_id,))
        await db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        await db.commit()

# --- ПЕРЕВІРКА НА КОНФЛІКТ ---
async def get_client_id_by_phone(phone_number):
    """Повертає ID клієнта, якщо знайдено за нормалізованим номером, або None."""
    
    # 1. Нормалізуємо вхідний номер для пошуку
    normalized_phone = normalize_phone(phone_number)
    if not normalized_phone:
        return None
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Шукаємо точний збіг нормалізованого номера
        sql = "SELECT client_id FROM phones WHERE phone_number = ? LIMIT 1"
        async with db.execute(sql, (normalized_phone,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else None


# --- ОТРИМАННЯ ДАНИХ ТА ПОШУК (Retrieve & Search) ---

# ВИПРАВЛЕНА ФУНКЦІЯ
async def search_by_text(query):
    query = query.strip()
    if not query:
        return []

    # 1. Спроба нормалізувати запит для пошуку в номерах
    normalized_phone = normalize_phone(query)
    
    # 2. Підготовка умов WHERE та параметрів
    conditions = []
    params = []
    
    # Умова 1: Завжди шукаємо в нотатках (використовуємо оригінальний запит)
    conditions.append("c.note LIKE ?")
    params.append(f"%{query}%")
    
    # Умова 2: Шукаємо в номерах ТІЛЬКИ, якщо нормалізація була успішною
    # (Тобто, якщо запит містив достатньо цифр, щоб normalize_phone повернув результат)
    if normalized_phone and len(''.join(filter(str.isdigit, normalized_phone))) > 1:
        
        # Видаляємо '+' для максимального збігу, оскільки в базі може бути і без нього
        search_digits = normalized_phone.replace('+', '')
        
        conditions.append("p.phone_number LIKE ?")
        params.append(f"%{search_digits}%")
    
    # Об'єднуємо умови (буде 'c.note LIKE ?' або 'c.note LIKE ? OR p.phone_number LIKE ?')
    where_clause = " OR ".join(conditions)
    
    sql = f"""
        SELECT DISTINCT c.id 
        FROM clients c
        LEFT JOIN phones p ON p.client_id = c.id
        WHERE {where_clause}
    """
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Виконуємо запит з динамічним набором параметрів
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
            
            
async def get_client_full_info(client_id):
    async with aiosqlite.connect(DB_PATH) as db:
        # Отримуємо нотатку
        async with db.execute("SELECT note FROM clients WHERE id = ?", (client_id,)) as cursor:
            res = await cursor.fetchone()
            if not res: return None
            note = res[0]
        
        # Отримуємо телефони
        phones = []
        async with db.execute("SELECT phone_number FROM phones WHERE client_id = ?", (client_id,)) as cursor:
            rows = await cursor.fetchall()
            phones = [r[0] for r in rows]
            
        # Отримуємо ID першого фото для відображення
        photo_file_id = None
        async with db.execute("SELECT file_id FROM faces WHERE client_id = ? AND file_id IS NOT NULL LIMIT 1", (client_id,)) as cursor:
            res = await cursor.fetchone()
            if res: photo_file_id = res[0]
            
        return {"id": client_id, "note": note, "phones": phones, "photo_file_id": photo_file_id}

async def get_all_face_encodings():
    """Повертає список словників: {client_id, encoding, file_id}"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT client_id, encoding, file_id FROM faces") as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "client_id": row[0],
                    "encoding": pickle.loads(row[1]),
                    "file_id": row[2]
                })
            return results