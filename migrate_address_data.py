#!/usr/bin/env python
"""
Скрипт для переноса данных из поля address в отдельные поля city, street, house_number
"""

import os
import sys
import django
import re

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autoservice.settings')
django.setup()

from core.models import AutoService

def parse_address(address):
    """
    Парсит адрес и возвращает город, улицу и номер дома
    """
    if not address:
        return '', '', ''
    
    # Очищаем адрес от лишних пробелов
    address = address.strip()
    
    # Паттерны для парсинга
    patterns = [
        # г. Москва, ул. Ленина, д. 10А
        r'г\.\s*([^,]+),\s*ул\.\s*([^,]+),\s*д\.\s*(\S+)',
        # г. Москва, ул. Ленина 10А
        r'г\.\s*([^,]+),\s*ул\.\s*(.+?)\s+(\d+\w*)',
        # Москва, ул. Ленина, 10А
        r'([^,]+),\s*ул\.\s*([^,]+),\s*(\S+)',
        # Москва, Ленина, 10А
        r'([^,]+),\s*([^,]+),\s*(\S+)',
        # г. Москва ул. Ленина 10А
        r'г\.\s*(\S+)\s+ул\.\s*(.+?)\s+(\d+\w*)',
        # Москва ул. Ленина 10А
        r'(\S+)\s+ул\.\s*(.+?)\s+(\d+\w*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            street = match.group(2).strip()
            house = match.group(3).strip()
            
            # Очищаем от лишних символов
            city = re.sub(r'^г\.?\s*', '', city)
            street = re.sub(r'^ул\.?\s*', '', street)
            house = re.sub(r'^д\.?\s*', '', house)
            
            return city, street, house
    
    # Если не удалось распарсить, пытаемся разделить по запятым
    parts = [part.strip() for part in address.split(',')]
    if len(parts) >= 3:
        city = re.sub(r'^г\.?\s*', '', parts[0])
        street = re.sub(r'^ул\.?\s*', '', parts[1])
        house = re.sub(r'^д\.?\s*', '', parts[2])
        return city, street, house
    elif len(parts) == 2:
        # Возможно город и улица с домом
        city = re.sub(r'^г\.?\s*', '', parts[0])
        street_house = parts[1]
        
        # Пытаемся выделить номер дома из конца строки
        match = re.search(r'(.+?)\s+(\d+\w*)$', street_house)
        if match:
            street = re.sub(r'^ул\.?\s*', '', match.group(1))
            house = match.group(2)
            return city, street, house
        else:
            return city, street_house, ''
    
    # Если ничего не получилось, возвращаем весь адрес как есть
    return address, '', ''

def migrate_address_data():
    """
    Переносит данные из поля address в отдельные поля
    """
    autoservices = AutoService.objects.all()
    updated_count = 0
    
    print(f"Найдено {autoservices.count()} автосервисов для обработки...")
    
    for autoservice in autoservices:
        if autoservice.address and not (autoservice.city or autoservice.street or autoservice.house_number):
            print(f"\nОбрабатываем: {autoservice.name}")
            print(f"Исходный адрес: {autoservice.address}")
            
            city, street, house_number = parse_address(autoservice.address)
            
            print(f"Результат парсинга:")
            print(f"  Город: '{city}'")
            print(f"  Улица: '{street}'")
            print(f"  Дом: '{house_number}'")
            
            # Обновляем поля
            autoservice.city = city
            autoservice.street = street
            autoservice.house_number = house_number
            
            # save() автоматически обновит поле address через метод get_full_address()
            autoservice.save()
            
            updated_count += 1
            
            print(f"Новый адрес: {autoservice.get_full_address()}")
        else:
            print(f"Пропускаем {autoservice.name} (нет адреса или уже обработан)")
    
    print(f"\n✅ Обработано {updated_count} автосервисов")
    
if __name__ == '__main__':
    migrate_address_data()
