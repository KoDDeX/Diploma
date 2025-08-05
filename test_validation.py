"""
Тестирование валидации графика работы
"""
import os
import sys
import django

# Настройка Django окружения
sys.path.append('z:/Обучение/Top. Python/Diploma')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autoservice.settings')
django.setup()

from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, time, timedelta
from core.models import WorkSchedule
from core.forms import WorkScheduleForm
from users.models import User

def test_schedule_validation():
    """Тестирование различных сценариев валидации"""
    
    print("🔧 Тестирование валидации графика работы")
    print("=" * 50)
    
    # Попробуем найти мастера для тестов
    try:
        master = User.objects.filter(role='master').first()
        if not master:
            print("❌ Не найден мастер для тестирования")
            return
        
        print(f"✅ Используем мастера: {master.get_full_name() or master.username}")
        
        # Тест 1: Валидация дат
        print("\n📅 Тест 1: Валидация дат")
        
        # Дата окончания раньше начала
        try:
            schedule_data = {
                'master': master.id,
                'schedule_type': 'weekly',
                'start_date': date.today() + timedelta(days=7),
                'end_date': date.today() + timedelta(days=3),  # Раньше начала
                'start_time': time(9, 0),
                'end_time': time(18, 0),
                'is_active': True
            }
            
            form = WorkScheduleForm(schedule_data, autoservice=master.autoservice)
            if form.is_valid():
                print("❌ Форма должна быть невалидной (дата окончания раньше начала)")
            else:
                print("✅ Корректно отклонена форма с неправильными датами")
                print(f"   Ошибки: {form.errors}")
        except Exception as e:
            print(f"❌ Ошибка в тесте 1: {e}")
        
        # Тест 2: Валидация времени
        print("\n⏰ Тест 2: Валидация времени")
        
        try:
            schedule_data = {
                'master': master.id,
                'schedule_type': 'weekly',
                'start_date': date.today() + timedelta(days=1),
                'end_date': date.today() + timedelta(days=30),
                'start_time': time(18, 0),  # После окончания
                'end_time': time(9, 0),     # До начала
                'is_active': True
            }
            
            form = WorkScheduleForm(schedule_data, autoservice=master.autoservice)
            if form.is_valid():
                print("❌ Форма должна быть невалидной (время окончания раньше начала)")
            else:
                print("✅ Корректно отклонена форма с неправильным временем")
                print(f"   Ошибки: {form.errors}")
        except Exception as e:
            print(f"❌ Ошибка в тесте 2: {e}")
        
        # Тест 3: Слишком длинный рабочий день
        print("\n🕐 Тест 3: Слишком длинный рабочий день")
        
        try:
            schedule_data = {
                'master': master.id,
                'schedule_type': 'weekly',
                'start_date': date.today() + timedelta(days=1),
                'end_date': date.today() + timedelta(days=30),
                'start_time': time(6, 0),   # 6:00
                'end_time': time(23, 0),    # 23:00 (17 часов)
                'is_active': True
            }
            
            form = WorkScheduleForm(schedule_data, autoservice=master.autoservice)
            if form.is_valid():
                print("❌ Форма должна быть невалидной (слишком длинный день)")
            else:
                print("✅ Корректно отклонена форма со слишком длинным днем")
                print(f"   Ошибки: {form.errors}")
        except Exception as e:
            print(f"❌ Ошибка в тесте 3: {e}")
        
        # Тест 4: Валидный график
        print("\n✅ Тест 4: Валидный график")
        
        try:
            schedule_data = {
                'master': master.id,
                'schedule_type': 'weekly',
                'start_date': date.today() + timedelta(days=1),
                'end_date': date.today() + timedelta(days=30),
                'start_time': time(9, 0),
                'end_time': time(18, 0),
                'is_active': True
            }
            
            form = WorkScheduleForm(schedule_data, autoservice=master.autoservice)
            if form.is_valid():
                print("✅ Валидная форма принята")
                # Не сохраняем, только тестируем
            else:
                print("❌ Валидная форма отклонена")
                print(f"   Ошибки: {form.errors}")
        except Exception as e:
            print(f"❌ Ошибка в тесте 4: {e}")
        
        print("\n" + "=" * 50)
        print("🎯 Тестирование завершено")
        
    except Exception as e:
        print(f"❌ Общая ошибка тестирования: {e}")

if __name__ == "__main__":
    test_schedule_validation()
