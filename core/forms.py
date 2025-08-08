from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from transliterate import translit
from .models import (
    AutoService,
    Region,
    Service,
    ServiceCategory,
    StandardService,
    Order,
    Car,
    WorkSchedule,
    Review,
    ReviewReply,
)

User = get_user_model()


def generate_slug_from_name(name):
    """Генерирует slug из названия с транслитерацией русских символов"""
    try:
        # Пытаемся транслитерировать русский текст
        transliterated = translit(name, 'ru', reversed=True)
        slug = slugify(transliterated)
    except Exception:
        # Если транслитерация не удалась, используем стандартный slugify
        slug = slugify(name)
    
    # Если slug пустой (например, только цифры или спец. символы), используем fallback
    if not slug:
        slug = 'autoservice'
    
    return slug


class AutoServiceEditForm(forms.ModelForm):
    """Форма редактирования автосервиса"""

    class Meta:
        model = AutoService
        fields = [
            "name",
            "region",
            "city",
            "street", 
            "house_number",
            "phone",
            "email",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Название автосервиса",
                }
            ),
            "region": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Москва",
                }
            ),
            "street": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "ул. Ленина",
                }
            ),
            "house_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "10А",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "+7 (XXX) XXX-XX-XX",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "email@autoservice.ru",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Краткое описание услуг и особенностей автосервиса",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }
        labels = {
            "name": "Название автосервиса",
            "region": "Регион",
            "city": "Город",
            "street": "Улица",
            "house_number": "Номер дома",
            "phone": "Телефон",
            "email": "Email",
            "description": "Описание",
            "is_active": "Автосервис активен",
        }

    def save(self, commit=True):
        """Сохраняем автосервис с обновлением slug при изменении названия"""
        autoservice = super().save(commit=False)
        
        # Проверяем, изменилось ли название
        if self.instance.pk and 'name' in self.changed_data:
            # Генерируем новый уникальный slug
            base_slug = generate_slug_from_name(autoservice.name)
            slug = base_slug
            counter = 1

            while AutoService.objects.filter(slug=slug).exclude(pk=autoservice.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            autoservice.slug = slug

        if commit:
            autoservice.save()

        return autoservice


class AddManagerForm(forms.Form):
    """Форма добавления менеджера"""

    email = forms.EmailField(
        label="Email пользователя",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "user@example.com",
            }
        ),
        help_text="Введите email зарегистрированного пользователя",
    )

    role = forms.ChoiceField(
        label="Роль",
        choices=[],  # Будет установлено в __init__
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        help_text="Выберите роль для нового сотрудника",
    )

    def __init__(self, *args, **kwargs):
        self.autoservice = kwargs.pop("autoservice", None)
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)
        
        # Определяем доступные роли в зависимости от роли текущего пользователя
        if self.current_user:
            manageable_roles = self.current_user.can_manage_users()
            role_choices = [(key, value) for key, value in User.ROLE_CHOICES if key in manageable_roles]
            self.fields['role'].choices = role_choices
            
            # Устанавливаем начальное значение
            if 'master' in manageable_roles:
                self.fields['role'].initial = 'master'
            elif 'manager' in manageable_roles:
                self.fields['role'].initial = 'manager'

    def clean_email(self):
        email = self.cleaned_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise forms.ValidationError("Пользователь с таким email не найден")

        # Проверяем, не является ли пользователь уже сотрудником этого автосервиса
        if user.autoservice == self.autoservice:
            raise forms.ValidationError(
                "Пользователь уже является сотрудником данного автосервиса"
            )

        # Проверяем, не является ли пользователь сотрудником другого автосервиса
        if user.autoservice and user.autoservice != self.autoservice:
            raise forms.ValidationError(
                f'Пользователь уже работает в автосервисе "{user.autoservice.name}"'
            )

        # Проверяем, не является ли пользователь суперадминистратором
        if user.role == "super_admin":
            raise forms.ValidationError(
                "Нельзя назначить суперадминистратора менеджером автосервиса"
            )

        return email

    def get_user(self):
        """Возвращает пользователя по email из cleaned_data"""
        email = self.cleaned_data.get("email")
        if email:
            try:
                return User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:
                return None
        return None


class AutoServiceRegistrationForm(forms.ModelForm):
    """Форма регистрации нового автосервиса"""

    class Meta:
        model = AutoService
        fields = [
            "name",
            "region",
            "city",
            "street",
            "house_number",
            "phone",
            "email",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "required": True,
                }
            ),
            "region": forms.Select(
                attrs={
                    "class": "form-select form-select-lg",
                    "required": True,
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "required": True,
                }
            ),
            "street": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "required": True,
                }
            ),
            "house_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "required": True,
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "required": True,
                    "id": "phone-input",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "required": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }
        labels = {
            "name": "Название автосервиса *",
            "region": "Регион *",
            "city": "Город *",
            "street": "Улица *",
            "house_number": "Номер дома *",
            "phone": "Телефон *",
            "email": "Email *",
            "description": "Описание услуг",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем пустой вариант для региона
        self.fields["region"].empty_label = "Выберите регион"

    def clean_name(self):
        name = self.cleaned_data["name"]

        # Проверяем, не существует ли уже автосервис с таким названием в том же регионе
        region = self.cleaned_data.get("region")
        if region:
            if AutoService.objects.filter(name=name, region=region).exists():
                raise forms.ValidationError(
                    f'Автосервис с названием "{name}" уже существует в регионе {region.name}'
                )

        return name

    def clean_email(self):
        email = self.cleaned_data["email"]

        # Проверяем, не используется ли уже этот email
        if AutoService.objects.filter(email=email).exists():
            raise forms.ValidationError("Автосервис с таким email уже зарегистрирован")

        return email

    def save(self, commit=True):
        """Создаём автосервис с автоматически сгенерированным slug и статусом неактивен"""
        autoservice = super().save(commit=False)

        # Генерируем уникальный slug с транслитерацией
        base_slug = generate_slug_from_name(autoservice.name)
        slug = base_slug
        counter = 1

        while AutoService.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        autoservice.slug = slug
        autoservice.is_active = False  # По умолчанию неактивен до модерации

        if commit:
            autoservice.save()

        return autoservice


class ServiceCreateForm(forms.ModelForm):
    """Форма создания услуги администратором автосервиса"""

    class Meta:
        model = Service
        fields = [
            "standard_service",
            "name",
            "description",
            "price",
            "duration",
            "is_popular",
            "is_active",
            "image",
        ]
        widgets = {
            "standard_service": forms.Select(
                attrs={
                    "class": "form-select",
                    "id": "id_standard_service",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Название услуги",
                    "id": "id_name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Подробное описание услуги, что входит в работу, особенности",
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "0",
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "duration": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "60",
                    "min": "1",
                    "step": "1",
                    "id": "id_duration",
                }
            ),
            "is_popular": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "image": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                }
            ),
        }
        labels = {
            "standard_service": "Стандартная услуга",
            "name": "Название услуги",
            "description": "Описание",
            "price": "Цена (руб.)",
            "duration": "Длительность (мин.)",
            "is_popular": "Популярная услуга",
            "is_active": "Услуга активна",
            "image": "Изображение услуги",
        }

    def __init__(self, *args, **kwargs):
        self.autoservice = kwargs.pop("autoservice", None)
        super().__init__(*args, **kwargs)

        # Добавляем пустой вариант для стандартной услуги
        self.fields["standard_service"].empty_label = "Выберите стандартную услугу"

        # Группируем стандартные услуги по категориям для удобства выбора
        standard_services = StandardService.objects.select_related("category").order_by(
            "category__name", "name"
        )
        choices = [("", "Выберите стандартную услугу")]

        current_category = None
        for service in standard_services:
            if service.category != current_category:
                if current_category is not None:
                    choices.append(("", "─" * 30))  # Разделитель
                choices.append(("", f"📁 {service.category.name}"))
                current_category = service.category

            # Добавляем информацию о типичной цене и длительности на основе реальных данных
            services_count = service.get_services_count()
            if services_count > 0:
                price_info = service.get_typical_price_display()
                duration_info = service.get_typical_duration_display()
                extra_info = (
                    f" ({duration_info}, {price_info}, {services_count} автосервисов)"
                )
            else:
                extra_info = " (новая услуга)"

            choices.append((service.id, f"  └ {service.name}{extra_info}"))

        self.fields["standard_service"].choices = choices

        # Устанавливаем начальные значения
        self.fields["is_active"].initial = True

    def clean(self):
        cleaned_data = super().clean()
        standard_service = cleaned_data.get("standard_service")
        duration = cleaned_data.get("duration")
        price = cleaned_data.get("price")

        # Базовые проверки
        if duration and duration <= 0:
            self.add_error("duration", "Длительность должна быть больше 0 минут")

        if price and price <= 0:
            self.add_error("price", "Цена должна быть больше 0 рублей")

        # Информационные сообщения (не блокирующие)
        if standard_service and duration:
            min_duration, max_duration = standard_service.get_duration_range()

            if min_duration and max_duration:
                # Безопасное преобразование для сравнения
                min_threshold = int(float(min_duration) * 0.3)
                max_threshold = int(float(max_duration) * 3)

                # Показываем только информацию, не блокируем
                if duration < min_threshold or duration > max_threshold:
                    # Очень сильное отклонение - показываем предупреждение в консоли
                    print(
                        f"ПРЕДУПРЕЖДЕНИЕ: Длительность {duration} мин сильно отличается от обычной для '{standard_service.name}' ({min_duration}-{max_duration} мин)"
                    )

        if standard_service and price:
            min_price, max_price = standard_service.get_price_range()

            if min_price and max_price:
                # Используем Decimal для безопасного сравнения
                from decimal import Decimal

                # Преобразуем в Decimal для корректных вычислений
                min_price_decimal = (
                    Decimal(str(min_price))
                    if not isinstance(min_price, Decimal)
                    else min_price
                )
                max_price_decimal = (
                    Decimal(str(max_price))
                    if not isinstance(max_price, Decimal)
                    else max_price
                )

                min_threshold = min_price_decimal * Decimal("0.1")
                max_threshold = max_price_decimal * Decimal("10")

                # Показываем только информацию, не блокируем
                if price < min_threshold or price > max_threshold:
                    # Очень сильное отклонение - показываем предупреждение в консоли
                    print(
                        f"ПРЕДУПРЕЖДЕНИЕ: Цена {price} руб сильно отличается от обычной для '{standard_service.name}' ({min_price}-{max_price} руб)"
                    )

        return cleaned_data

    def save(self, commit=True):
        """Сохраняем услугу с привязкой к автосервису"""
        service = super().save(commit=False)
        service.autoservice = self.autoservice

        if commit:
            service.save()

        return service


class CarForm(forms.ModelForm):
    """Форма для добавления/редактирования автомобиля"""
    
    class Meta:
        model = Car
        fields = ['brand', 'model', 'year', 'number', 'is_default']
        widgets = {
            'brand': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Например: Toyota, BMW, Lada',
                }
            ),
            'model': forms.TextInput(
                attrs={
                    'class': 'form-control', 
                    'placeholder': 'Например: Camry, X5, Granta',
                }
            ),
            'year': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': '2020',
                    'min': '1980',
                    'max': '2025',
                }
            ),
            'number': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'А123БВ777 (необязательно)',
                }
            ),
            'is_default': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                }
            ),
        }
        labels = {
            'brand': 'Марка автомобиля *',
            'model': 'Модель автомобиля *', 
            'year': 'Год выпуска *',
            'number': 'Государственный номер',
            'is_default': 'Сделать основным автомобилем',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Обновляем максимальный год
        from datetime import date
        current_year = date.today().year
        self.fields['year'].widget.attrs['max'] = str(current_year + 1)
    
    def clean_year(self):
        year = self.cleaned_data['year']
        from datetime import date
        
        current_year = date.today().year
        if year < 1980:
            raise forms.ValidationError('Год выпуска не может быть раньше 1980')
        if year > current_year + 1:
            raise forms.ValidationError(f'Год выпуска не может быть больше {current_year + 1}')
            
        return year
    
    def save(self, commit=True):
        car = super().save(commit=False)
        if self.user:
            car.owner = self.user
        
        if commit:
            car.save()
            
        return car


class OrderCreateForm(forms.ModelForm):
    """Форма создания заказа клиентом"""
    
    # Поле для выбора сохраненного автомобиля
    saved_car = forms.ModelChoiceField(
        queryset=Car.objects.none(),
        required=False,
        empty_label="Выбрать из сохраненных автомобилей...",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label="Сохраненный автомобиль"
    )
    
    # Поле для выбора мастера
    preferred_master = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="Мастер будет назначен менеджером автосервиса",
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg',
            'id': 'preferred_master_select'
        }),
        label="Предпочитаемый мастер (необязательно)"
    )

    class Meta:
        model = Order
        fields = [
            "saved_car",
            "car_brand",
            "car_model", 
            "car_year",
            "car_number",
            "description",
            "preferred_date",
            "preferred_time",
            "preferred_master",
        ]
        widgets = {
            "car_brand": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Например: Toyota, BMW, Lada",
                }
            ),
            "car_model": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg", 
                    "placeholder": "Например: Camry, X5, Granta",
                }
            ),
            "car_year": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "2020",
                    "min": "1980",
                    "max": "2025",
                }
            ),
            "car_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "А123БВ777 (необязательно)",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Опишите проблему, особые пожелания или дополнительную информацию...",
                }
            ),
            "preferred_date": forms.DateInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "type": "date",
                    "min": "",  # Будет установлено в JavaScript
                }
            ),
            "preferred_time": forms.TimeInput(
                attrs={
                    "class": "form-control form-control-lg", 
                    "type": "time",
                    "min": "08:00",
                    "max": "20:00", 
                }
            ),
        }
        labels = {
            "car_brand": "Марка автомобиля *",
            "car_model": "Модель автомобиля *", 
            "car_year": "Год выпуска *",
            "car_number": "Государственный номер",
            "description": "Описание проблемы",
            "preferred_date": "Предпочтительная дата *",
            "preferred_time": "Удобное время *",
            "preferred_master": "Предпочитаемый мастер",
        }

    def __init__(self, *args, **kwargs):
        self.service = kwargs.pop("service", None)
        self.user = kwargs.pop("user", None)
        self.autoservice = kwargs.pop("autoservice", None)
        super().__init__(*args, **kwargs)

        # Устанавливаем минимальную дату на завтра
        from datetime import date, timedelta

        tomorrow = date.today() + timedelta(days=1)
        self.fields["preferred_date"].widget.attrs["min"] = tomorrow.strftime(
            "%Y-%m-%d"
        )

        # Устанавливаем начальные значения
        self.fields["preferred_time"].initial = "10:00"
        
        # Настраиваем queryset для доступных мастеров
        if self.autoservice:
            from users.models import User
            available_masters = User.objects.filter(
                autoservice=self.autoservice,
                role='master',
                is_active=True
            ).order_by('last_name', 'first_name', 'username')
            self.fields["preferred_master"].queryset = available_masters
            # Переопределяем отображение мастеров в выпадающем списке
            self.fields["preferred_master"].label_from_instance = lambda obj: obj.get_full_name()
        
        # Настраиваем queryset для сохраненных автомобилей пользователя
        if self.user and self.user.is_authenticated:
            self.fields["saved_car"].queryset = Car.objects.filter(owner=self.user).order_by('-is_default', '-created_at')
            
            # Если у пользователя есть основной автомобиль, выбираем его по умолчанию
            default_car = Car.objects.filter(owner=self.user, is_default=True).first()
            if default_car:
                self.fields["saved_car"].initial = default_car
                # Предзаполняем поля данными основного автомобиля
                self.fields["car_brand"].initial = default_car.brand
                self.fields["car_model"].initial = default_car.model  
                self.fields["car_year"].initial = default_car.year
                self.fields["car_number"].initial = default_car.number
        else:
            # Для неавторизованных пользователей скрываем поле выбора
            self.fields.pop("saved_car")

    def clean_car_year(self):
        year = self.cleaned_data["car_year"]
        from datetime import date

        current_year = date.today().year
        if year < 1980:
            raise forms.ValidationError("Год выпуска не может быть раньше 1980")
        if year > current_year + 1:
            raise forms.ValidationError(
                f"Год выпуска не может быть больше {current_year + 1}"
            )

        return year

    def clean_preferred_date(self):
        preferred_date = self.cleaned_data["preferred_date"]
        from datetime import date

        if preferred_date <= date.today():
            raise forms.ValidationError("Выберите дату не раньше завтрашнего дня")

        return preferred_date

    def save(self, commit=True):
        """Сохраняем заказ с привязкой к услуге и пользователю"""
        order = super().save(commit=False)
        order.service = self.service
        order.client = self.user
        
        # Если выбран сохраненный автомобиль, связываем его с заказом
        saved_car = self.cleaned_data.get('saved_car')
        if saved_car:
            order.car = saved_car

        if commit:
            order.save()
            
            # Всегда устанавливаем автосервис из последнего заказа
            if self.user and self.autoservice:
                self.user.autoservice = self.autoservice
                self.user.save(update_fields=['autoservice'])

        return order


class WorkScheduleForm(forms.ModelForm):
    """Форма для создания и редактирования графика работы мастера"""
    
    class Meta:
        model = WorkSchedule
        fields = ['master', 'schedule_type', 'start_date', 'end_date', 
                 'custom_days', 'start_time', 'end_time', 'is_active']
        widgets = {
            'master': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'schedule_type': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'required': True
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'custom_days': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: 1,3,5 (Пн, Ср, Пт)',
                'help_text': 'Дни недели через запятую: 1-Пн, 2-Вт, 3-Ср, 4-Чт, 5-Пт, 6-Сб, 7-Вс'
            }),
            'start_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control',
                'required': True
            }),
            'end_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control', 
                'required': True
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'master': 'Мастер',
            'schedule_type': 'Тип графика',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания',
            'custom_days': 'Дни недели',
            'start_time': 'Время начала работы',
            'end_time': 'Время окончания работы',
            'is_active': 'Активный график'
        }

    def __init__(self, *args, **kwargs):
        self.autoservice = kwargs.pop('autoservice', None)
        super().__init__(*args, **kwargs)
        
        # Фильтруем мастеров только текущего автосервиса
        if self.autoservice:
            from users.models import User
            self.fields['master'].queryset = User.objects.filter(
                role='master',
                autoservice=self.autoservice
            )
        
        # Переопределяем отображение мастеров в выпадающем списке
        self.fields['master'].label_from_instance = lambda obj: obj.get_full_name()
        
        # Устанавливаем начальные значения
        self.fields['start_time'].initial = '09:00'
        self.fields['end_time'].initial = '18:00'
        self.fields['is_active'].initial = True
        
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        schedule_type = cleaned_data.get('schedule_type')
        master = cleaned_data.get('master')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        custom_days = cleaned_data.get('custom_days')
        
        # 1. Базовые проверки дат
        if start_date and end_date:
            # Дата окончания не может быть раньше даты начала
            if end_date < start_date:
                raise ValidationError('Дата окончания не может быть раньше даты начала')
            
            # Дата начала не может быть в прошлом (кроме сегодня)
            if start_date < timezone.now().date():
                raise ValidationError('Дата начала не может быть в прошлом')
            
            # Максимальный период графика - 1 год
            if (end_date - start_date).days > 365:
                raise ValidationError('Максимальный период графика - 1 год')
        
        # 2. Проверки для недельного графика
        if schedule_type == 'weekly':
            # Для недельного графика рекомендуем минимум 2 недели
            if start_date and end_date and (end_date - start_date).days < 14:
                self.add_error('end_date', 'Для недельного графика рекомендуется период не менее 2 недель')
        
        # 3. Проверки для пользовательского графика
        if schedule_type == 'custom':
            # Для пользовательского графика максимум 3 месяца
            if start_date and end_date and (end_date - start_date).days > 90:
                raise ValidationError('Для пользовательского графика максимальный период - 3 месяца')
            
            # Проверяем корректность дней недели
            if custom_days:
                try:
                    days = [int(day.strip()) for day in custom_days.split(',')]
                    if not all(1 <= day <= 7 for day in days):
                        raise ValueError()
                    if not days:
                        raise ValidationError('Должен быть выбран хотя бы один рабочий день')
                    if len(days) == 7:
                        self.add_error('custom_days', 'Рекомендуется предусмотреть выходные дни')
                except (ValueError, AttributeError):
                    raise ValidationError('Дни недели должны быть числами от 1 до 7, разделенными запятыми')
        
        # 4. Проверка пересечений с существующими графиками
        if master and start_date and end_date:
            overlapping_schedules = WorkSchedule.objects.filter(
                master=master,
                is_active=True
            )
            
            # Исключаем текущий график при редактировании
            if self.instance.pk:
                overlapping_schedules = overlapping_schedules.exclude(pk=self.instance.pk)
            
            for schedule in overlapping_schedules:
                # Проверяем пересечение периодов
                if (start_date <= schedule.end_date and end_date >= schedule.start_date):
                    raise ValidationError(
                        f'График пересекается с существующим графиком '
                        f'({schedule.start_date.strftime("%d.%m.%Y")} - {schedule.end_date.strftime("%d.%m.%Y")})'
                    )
        
        # 5. Логические проверки времени работы
        if start_time and end_time:
            # Время окончания должно быть позже времени начала
            if end_time <= start_time:
                raise ValidationError('Время окончания работы должно быть позже времени начала')
            
            # Проверяем разумность рабочего дня (не более 12 часов)
            start_datetime = datetime.combine(datetime.today(), start_time)
            end_datetime = datetime.combine(datetime.today(), end_time)
            work_duration = (end_datetime - start_datetime).seconds / 3600
            
            if work_duration > 12:
                self.add_error('end_time', 'Рабочий день не может быть длиннее 12 часов')
            
            if work_duration < 1:
                self.add_error('end_time', 'Рабочий день должен быть не менее 1 часа')
        
        return cleaned_data


class ReviewForm(forms.ModelForm):
    """Базовая форма для создания отзыва"""
    
    class Meta:
        model = Review
        fields = ['rating', 'text', 'pros', 'cons']
        widgets = {
            'rating': forms.Select(attrs={
                'class': 'form-select form-select-lg',
                'required': True
            }),
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Напишите подробный отзыв...',
                'required': True
            }),
            'pros': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Что вам понравилось? (необязательно)'
            }),
            'cons': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Что можно улучшить? (необязательно)'
            })
        }
        labels = {
            'rating': 'Оценка *',
            'text': 'Текст отзыва *',
            'pros': 'Плюсы',
            'cons': 'Минусы'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Добавляем подсказки
        self.fields['rating'].help_text = 'Выберите оценку от 1 до 5 звезд'
        self.fields['text'].help_text = 'Поделитесь подробностями вашего опыта'


class AutoServiceReviewForm(ReviewForm):
    """Форма для отзыва об автосервисе"""
    
    def __init__(self, *args, **kwargs):
        self.autoservice = kwargs.pop('autoservice', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        review = super().save(commit=False)
        review.review_type = 'autoservice'
        review.autoservice = self.autoservice
        # Обязательно устанавливаем другие поля в None для валидации
        review.reviewed_user = None
        review.service = None
        
        if commit:
            review.save()
        return review


class MasterReviewForm(ReviewForm):
    """Форма для отзыва о мастере"""
    
    def __init__(self, *args, **kwargs):
        self.master = kwargs.pop('master', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        review = super().save(commit=False)
        review.review_type = 'master'
        review.reviewed_user = self.master
        # Обязательно устанавливаем другие поля в None для валидации
        review.autoservice = None
        review.service = None
        
        if commit:
            review.save()
        return review


class ServiceReviewForm(ReviewForm):
    """Форма для отзыва об услуге"""
    
    def __init__(self, *args, **kwargs):
        self.service = kwargs.pop('service', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        review = super().save(commit=False)
        review.review_type = 'service'
        review.service = self.service
        # Обязательно устанавливаем другие поля в None для валидации
        review.autoservice = None
        review.reviewed_user = None
        
        if commit:
            review.save()
        return review


class ReviewReplyForm(forms.ModelForm):
    """Форма для ответа на отзыв"""
    
    class Meta:
        model = ReviewReply
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Напишите ответ на отзыв...',
                'required': True
            })
        }
        labels = {
            'text': 'Ответ на отзыв *'
        }
    
    def __init__(self, *args, **kwargs):
        self.review = kwargs.pop('review', None)
        super().__init__(*args, **kwargs)
        self.fields['text'].help_text = 'Профессиональный ответ от имени автосервиса'
    
    def save(self, commit=True):
        reply = super().save(commit=False)
        reply.review = self.review
        if commit:
            reply.save()
        return reply



