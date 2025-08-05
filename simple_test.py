"""
Простой интерактивный тестер валидации
"""
import os
import sys
import django
from datetime import date, time, timedelta

# Настройка Django
sys.path.append('z:/Обучение/Top. Python/Diploma')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autoservice.settings')
django.setup()

from core.forms import WorkScheduleForm
from users.models import User

def test_specific_case():
    """Тестирование конкретного случая"""
    print("🔍 Тестирование конкретного случая валидации")
    print("=" * 50)
    
    # Найдем мастера
    master = User.objects.filter(role='master').first()
    if not master:
        print("❌ Мастер не найден!")
        return
    
    print(f"👨‍🔧 Мастер: {master.get_full_name() or master.username}")
    
    # Тестовые данные - ВАЛИДНЫЙ график
    schedule_data = {
        'master': master.id,
        'schedule_type': 'custom',
        'start_date': date.today() + timedelta(days=30),  # Будущая дата
        'end_date': date.today() + timedelta(days=60),    # Через 2 месяца
        'start_time': time(10, 0),   # 10:00
        'end_time': time(16, 0),     # 16:00 (6 часов)
        'custom_days': '1,3,5',      # Пн, Ср, Пт
        'is_active': True
    }
    
    print("\n📋 Тестовые данные:")
    print(f"   Период: {schedule_data['start_date']} - {schedule_data['end_date']}")
    print(f"   Время: {schedule_data['start_time']} - {schedule_data['end_time']}")
    print(f"   Дни: {schedule_data['custom_days']} (Понедельник, Среда, Пятница)")
    
    # Создаем форму
    form = WorkScheduleForm(schedule_data, autoservice=master.autoservice)
    
    print("\n🧪 Результат валидации:")
    if form.is_valid():
        print("✅ График ВАЛИДЕН!")
        print("   Все проверки пройдены успешно")
    else:
        print("❌ График НЕ валиден!")
        print("   Ошибки:")
        for field, errors in form.errors.items():
            print(f"   • {field}: {', '.join(errors)}")
    
    return form.is_valid()

if __name__ == "__main__":
    test_specific_case()
