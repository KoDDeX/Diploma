from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from .models import AutoService, Region, Service, ServiceCategory, StandardService

User = get_user_model()


class AutoServiceEditForm(forms.ModelForm):
    """Форма редактирования автосервиса"""

    class Meta:
        model = AutoService
        fields = [
            "name",
            "region",
            "address",
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
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Полный адрес автосервиса",
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
            "address": "Адрес",
            "phone": "Телефон",
            "email": "Email",
            "description": "Описание",
            "is_active": "Автосервис активен",
        }


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
        choices=[
            ("manager", "Менеджер"),
            ("autoservice_admin", "Администратор автосервиса"),
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        initial="manager",
        help_text="Выберите роль для нового сотрудника",
    )

    def __init__(self, *args, **kwargs):
        self.autoservice = kwargs.pop("autoservice", None)
        super().__init__(*args, **kwargs)

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
            "address",
            "phone",
            "email",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Название вашего автосервиса",
                    "required": True,
                }
            ),
            "region": forms.Select(
                attrs={
                    "class": "form-select form-select-lg",
                    "required": True,
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Полный адрес автосервиса с указанием города и улицы",
                    "required": True,
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "+7 (XXX) XXX-XX-XX",
                    "required": True,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "email@autoservice.ru",
                    "required": True,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Краткое описание ваших услуг, специализации и особенностей автосервиса",
                }
            ),
        }
        labels = {
            "name": "Название автосервиса *",
            "region": "Регион *",
            "address": "Адрес *",
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

        # Генерируем уникальный slug
        base_slug = slugify(autoservice.name)
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
                # Конвертируем в int для безопасного сравнения
                min_threshold = int(min_duration * 0.3)
                max_threshold = int(max_duration * 3)

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

                min_threshold = min_price * Decimal("0.1")
                max_threshold = max_price * Decimal("10")

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
