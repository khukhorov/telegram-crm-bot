# utils/data_cleaner.py (Новий файл)
import re
from typing import List

def normalize_phone_number(raw_number: str) -> str:
    """Видаляє всі символи, крім цифр та знака '+', залишаючи '+' на початку."""
    # 1. Видаляємо всі символи, крім цифр та знака '+'
    cleaned_number = re.sub(r'[^0-9\+]', '', raw_number)
    
    # 2. Якщо випадково ввели багато '+', залишаємо лише один на початку
    if cleaned_number.startswith('++'):
        cleaned_number = '+' + cleaned_number.lstrip('+')
        
    return cleaned_number

def normalize_phone_list(raw_phone_list: List[str]) -> List[str]:
    """Нормалізує список номерів та видаляє дублікати."""
    normalized_list = set()
    for num in raw_phone_list:
        normalized_list.add(normalize_phone_number(num))
    return list(normalized_list)
