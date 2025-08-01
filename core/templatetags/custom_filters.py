from django import template
from datetime import datetime, timedelta

register = template.Library()

@register.filter
def add_minutes(time_obj, minutes):
    """Добавляет минуты к времени"""
    if not time_obj or not minutes:
        return time_obj
    
    # Создаем datetime объект для сегодняшней даты с данным временем
    dt = datetime.combine(datetime.today().date(), time_obj)
    # Добавляем минуты
    dt += timedelta(minutes=int(minutes))
    # Возвращаем только время
    return dt.time()

@register.filter
def add_days(date_obj, days):
    """Добавляет дни к дате"""
    if not date_obj:
        return date_obj
    return date_obj + timedelta(days=int(days))

@register.filter
def get_item(dictionary, key):
    """Получает элемент из словаря по ключу"""
    return dictionary.get(key)

@register.filter
def format_duration(minutes):
    """Форматирует длительность в часы и минуты"""
    if not minutes:
        return "Не указано"
    
    minutes = int(minutes)
    if minutes >= 60:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes:
            return f"{hours} ч {remaining_minutes} мин"
        else:
            return f"{hours} ч"
    else:
        return f"{minutes} мин"

@register.filter
def split(value, delimiter):
    """Разделяет строку по разделителю"""
    if not value:
        return []
    return value.split(delimiter)
