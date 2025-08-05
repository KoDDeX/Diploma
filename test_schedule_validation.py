"""
Расширенное тестирование системы валидации графиков работы
"""
import os
import sys
import django
from datetime import date, time, timedelta
import argparse

# Настройка Django окружения
sys.path.append('z:/Обучение/Top. Python/Diploma')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autoservice.settings')
django.setup()

from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import WorkSchedule
from core.forms import WorkScheduleForm
from core.views import validate_schedule_business_logic
from users.models import User

class ScheduleValidationTester:
    """Класс для тестирования валидации графиков работы"""
    
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
        
    def log_test(self, test_name, passed, message="", error_details=""):
        """Логирование результата теста"""
        status = "✅" if passed else "❌"
        self.test_results.append({
            'name': test_name,
            'passed': passed,
            'message': message,
            'error_details': error_details
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{status} {test_name}: {message}")
        if error_details and not passed:
            print(f"   📝 Детали: {error_details}")
    
    def test_form_validation(self, master):
        """Тестирование валидации форм"""
        print("\n📋 Тестирование валидации форм")
        print("-" * 40)
        
        # Тест 1: Дата окончания раньше начала
        schedule_data = {
            'master': master.id,
            'schedule_type': 'weekly',
            'start_date': date.today() + timedelta(days=7),
            'end_date': date.today() + timedelta(days=3),
            'start_time': time(9, 0),
            'end_time': time(18, 0),
            'is_active': True
        }
        
        form = WorkScheduleForm(schedule_data, autoservice=master.autoservice)
        should_fail = not form.is_valid()
        self.log_test(
            "Дата окончания раньше начала",
            should_fail,
            "Корректно отклонено" if should_fail else "Неожиданно принято",
            str(form.errors) if not form.is_valid() else ""
        )
        
        # Тест 2: Слишком длинный рабочий день
        schedule_data = {
            'master': master.id,
            'schedule_type': 'weekly',
            'start_date': date.today() + timedelta(days=1),
            'end_date': date.today() + timedelta(days=30),
            'start_time': time(6, 0),
            'end_time': time(23, 0),  # 17 часов
            'is_active': True
        }
        
        form = WorkScheduleForm(schedule_data, autoservice=master.autoservice)
        should_fail = not form.is_valid()
        self.log_test(
            "Слишком длинный рабочий день (17 часов)",
            should_fail,
            "Корректно отклонено" if should_fail else "Неожиданно принято",
            str(form.errors) if not form.is_valid() else ""
        )
        
        # Тест 3: Дата в прошлом
        schedule_data = {
            'master': master.id,
            'schedule_type': 'weekly',
            'start_date': date.today() - timedelta(days=5),
            'end_date': date.today() + timedelta(days=30),
            'start_time': time(9, 0),
            'end_time': time(18, 0),
            'is_active': True
        }
        
        form = WorkScheduleForm(schedule_data, autoservice=master.autoservice)
        should_fail = not form.is_valid()
        self.log_test(
            "Дата начала в прошлом",
            should_fail,
            "Корректно отклонено" if should_fail else "Неожиданно принято",
            str(form.errors) if not form.is_valid() else ""
        )
    
    def test_business_logic(self, master):
        """Тестирование бизнес-логики"""
        print("\n💼 Тестирование бизнес-логики")
        print("-" * 40)
        
        # Создаем тестовый график
        test_schedule = WorkSchedule(
            master=master,
            schedule_type='custom',
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=30),
            start_time=time(9, 0),
            end_time=time(18, 0),
            custom_days='1,2,3,4,5,6,7',  # 7 дней в неделю
            is_active=True
        )
        
        # Тестируем предупреждение о переутомлении
        errors = validate_schedule_business_logic(test_schedule)
        has_warning = any('6 или более дней' in error for error in errors)
        
        self.log_test(
            "Предупреждение о переутомлении (7 дней в неделю)",
            has_warning,
            "Предупреждение выдано" if has_warning else "Предупреждение не выдано",
            f"Ошибки: {errors}" if errors else "Ошибок нет"
        )
    
    def test_model_validation(self, master):
        """Тестирование валидации модели"""
        print("\n🏗 Тестирование валидации модели")
        print("-" * 40)
        
        # Тест валидации на уровне модели
        schedule = WorkSchedule(
            master=master,
            schedule_type='weekly',
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=30),
            start_time=time(18, 0),  # Неправильное время
            end_time=time(9, 0),
            is_active=True
        )
        
        try:
            schedule.full_clean()
            self.log_test(
                "Валидация модели (неправильное время)",
                False,
                "Неожиданно прошла валидацию"
            )
        except ValidationError as e:
            self.log_test(
                "Валидация модели (неправильное время)",
                True,
                "Корректно отклонено валидацией модели",
                str(e)
            )
    
    def run_all_tests(self):
        """Запуск всех тестов"""
        print("🧪 ЗАПУСК ПОЛНОГО ТЕСТИРОВАНИЯ ВАЛИДАЦИИ")
        print("=" * 60)
        
        # Находим мастера для тестов
        master = User.objects.filter(role='master').first()
        if not master:
            print("❌ Не найден мастер для тестирования")
            return
        
        print(f"👨‍🔧 Используем мастера: {master.get_full_name() or master.username}")
        
        # Запускаем тесты
        self.test_form_validation(master)
        self.test_business_logic(master)
        self.test_model_validation(master)
        
        # Выводим итоги
        self.print_summary()
    
    def print_summary(self):
        """Вывод итогов тестирования"""
        print("\n" + "=" * 60)
        print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
        print("=" * 60)
        print(f"✅ Пройдено: {self.passed}")
        print(f"❌ Провалено: {self.failed}")
        print(f"📈 Процент успеха: {(self.passed / (self.passed + self.failed) * 100):.1f}%")
        
        if self.failed > 0:
            print("\n🔍 Провалившиеся тесты:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"   • {result['name']}: {result['message']}")
        
        print("\n🎯 Тестирование завершено!")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Тестирование валидации графиков работы')
    parser.add_argument('--quick', action='store_true', help='Быстрое тестирование')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
    
    args = parser.parse_args()
    
    tester = ScheduleValidationTester()
    
    if args.quick:
        print("⚡ Режим быстрого тестирования")
        # Можно добавить упрощенные тесты
    
    tester.run_all_tests()


if __name__ == "__main__":
    main()
