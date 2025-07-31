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
