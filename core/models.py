from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError


class ServiceCategory(models.Model):
    """Категории услуг (ТО, Ремонт двигателя, Шиномонтаж и т.д.)"""

    name = models.CharField(max_length=100, verbose_name="Название категории")
    slug = models.SlugField(unique=True, verbose_name="Слаг для URL")
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Bootstrap Icon класс",
        help_text="Например: bi-gear, bi-car-front и т.д.",
    )
    description = models.TextField(blank=True, verbose_name="Описание категории")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Категория услуг"
        verbose_name_plural = "Категории услуг"
        ordering = ["name"]

    def __str__(self):
        return self.name


class StandardService(models.Model):
    """Справочник стандартных услуг для унификации"""

    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name="standard_services",
        verbose_name="Категория",
    )
    name = models.CharField(max_length=200, verbose_name="Стандартное название")
    slug = models.SlugField(unique=True, verbose_name="Слаг для URL")
    description = models.TextField(verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Стандартная услуга"
        verbose_name_plural = "Стандартные услуги"
        ordering = ["category", "name"]
        unique_together = [["category", "slug"]]

    def __str__(self):
        return f"{self.category.name}: {self.name}"

    def get_price_range(self):
        """Возвращает диапазон цен на основе реальных услуг автосервисов"""
        services = self.autoservice_services.filter(is_active=True)
        if not services.exists():
            return None, None

        prices = services.values_list("price", flat=True)
        return min(prices), max(prices)

    def get_duration_range(self):
        """Возвращает диапазон времени на основе реальных услуг автосервисов"""
        services = self.autoservice_services.filter(is_active=True)
        if not services.exists():
            return None, None

        durations = services.values_list("duration", flat=True)
        return min(durations), max(durations)

    def get_typical_duration_display(self):
        """Возвращает диапазон времени в удобном формате на основе реальных данных"""
        min_duration, max_duration = self.get_duration_range()
        if min_duration is None or max_duration is None:
            return "Время не указано"

        if min_duration == max_duration:
            hours = min_duration // 60
            minutes = min_duration % 60
            if hours > 0:
                return f"{hours}ч {minutes}мин" if minutes > 0 else f"{hours}ч"
            return f"{minutes}мин"
        else:
            return f"{min_duration}-{max_duration} мин"

    def get_typical_price_display(self):
        """Возвращает диапазон цен в удобном формате на основе реальных данных"""
        min_price, max_price = self.get_price_range()
        if min_price is None or max_price is None:
            return "Цена не указана"

        if min_price == max_price:
            return f"{min_price} руб."
        else:
            return f"{min_price}-{max_price} руб."

    def get_average_price(self):
        """Возвращает среднюю цену услуги"""
        services = self.autoservice_services.filter(is_active=True)
        if not services.exists():
            return None

        from django.db.models import Avg
        from decimal import Decimal

        avg_price = services.aggregate(avg_price=Avg("price"))["avg_price"]
        if avg_price:
            # Конвертируем в Decimal и округляем
            return Decimal(str(round(float(avg_price), 2)))
        return None

    def get_services_count(self):
        """Возвращает количество автосервисов, предоставляющих эту услугу"""
        return self.autoservice_services.filter(is_active=True).count()

    @property
    def typical_duration_min(self):
        """Для обратной совместимости"""
        min_duration, _ = self.get_duration_range()
        return min_duration or 60

    @property
    def typical_duration_max(self):
        """Для обратной совместимости"""
        _, max_duration = self.get_duration_range()
        return max_duration or 60

    @property
    def typical_price_min(self):
        """Для обратной совместимости"""
        min_price, _ = self.get_price_range()
        return min_price

    @property
    def typical_price_max(self):
        """Для обратной совместимости"""
        _, max_price = self.get_price_range()
        return max_price


class Region(models.Model):
    """Регионы (города/области)"""

    name = models.CharField(max_length=100, verbose_name="Название региона")
    slug = models.SlugField(unique=True, verbose_name="Слаг для URL")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AutoService(models.Model):
    """Автосервисы"""

    name = models.CharField(max_length=200, verbose_name="Название автосервиса")
    slug = models.SlugField(unique=True, verbose_name="Слаг для URL")
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name="autoservices",
        verbose_name="Регион",
    )
    address = models.TextField(verbose_name="Адрес")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(verbose_name="Email")
    description = models.TextField(blank=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Автосервис"
        verbose_name_plural = "Автосервисы"
        unique_together = [["region", "slug"]]  # Уникальность в рамках региона
        ordering = ["region__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.region.name})"

    def get_absolute_url(self):
        return reverse(
            "core:autoservice_detail", kwargs={"autoservice_slug": self.slug}
        )


class Car(models.Model):
    """Автомобили пользователей"""
    
    owner = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name="cars",
        verbose_name="Владелец",
    )
    brand = models.CharField(max_length=50, verbose_name="Марка")
    model = models.CharField(max_length=50, verbose_name="Модель")
    year = models.PositiveIntegerField(verbose_name="Год выпуска")
    number = models.CharField(
        max_length=15,
        blank=True,
        verbose_name="Госномер",
        help_text="Государственный номер автомобиля (необязательно)",
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="Основной автомобиль",
        help_text="Будет выбираться автоматически при создании заказов"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    
    class Meta:
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"
        ordering = ["-is_default", "-created_at"]
        unique_together = [["owner", "brand", "model", "year"]]  # Уникальность для пользователя
    
    def __str__(self):
        car_info = f"{self.brand} {self.model} ({self.year})"
        if self.number:
            car_info += f" - {self.number}"
        return car_info
    
    def get_full_info(self):
        """Возвращает полную информацию об автомобиле"""
        return self.__str__()
    
    def save(self, *args, **kwargs):
        # Если это первый автомобиль пользователя или явно указан как основной
        if self.is_default:
            # Убираем флаг "основной" у других автомобилей пользователя
            Car.objects.filter(owner=self.owner, is_default=True).update(is_default=False)
        elif not Car.objects.filter(owner=self.owner).exists():
            # Если это первый автомобиль, делаем его основным
            self.is_default = True
            
        super().save(*args, **kwargs)


class Service(models.Model):
    """Услуги автосервиса"""

    autoservice = models.ForeignKey(
        AutoService,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name="Автосервис",
    )
    # Связь со стандартной услугой для унификации и поиска
    standard_service = models.ForeignKey(
        StandardService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="autoservice_services",
        verbose_name="Стандартная услуга",
        help_text="Выберите из справочника для возможности сравнения с другими автосервисами",
    )
    name = models.CharField(max_length=200, verbose_name="Название услуги")
    description = models.TextField(verbose_name="Описание")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена (руб.)",
        help_text="Цена в рублях",
    )
    duration = models.PositiveIntegerField(
        verbose_name="Длительность (мин)",
        help_text="Время выполнения в минутах",
        default=30,
    )
    is_popular = models.BooleanField(
        verbose_name="Популярная услуга",
        default=False,
        help_text="Отмечать популярные услуги для выделения",
    )
    is_active = models.BooleanField(
        default=True, verbose_name="Активна", help_text="Доступна ли услуга для заказа"
    )
    image = models.ImageField(
        upload_to="services/",
        verbose_name="Изображение",
        blank=True,
        help_text="Фото для демонстрации услуги",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата изменения")

    def __str__(self):
        return f"{self.autoservice.name}: {self.name} - {self.price} руб."

    def get_duration_display(self):
        """Возвращает длительность в удобном формате"""
        hours = self.duration // 60
        minutes = self.duration % 60
        if hours > 0:
            return f"{hours}ч {minutes}мин" if minutes > 0 else f"{hours}ч"
        return f"{minutes}мин"

    @property
    def category(self):
        """Получить категорию через стандартную услугу"""
        return self.standard_service.category if self.standard_service else None

    def clean(self):
        """Валидация данных"""
        super().clean()

        # Базовые проверки с правильными типами данных
        if self.duration is not None and self.duration <= 0:
            raise ValidationError(
                {"duration": "Длительность должна быть больше 0 минут"}
            )

        if self.price is not None and self.price <= 0:
            raise ValidationError({"price": "Цена должна быть больше 0 рублей"})

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["-is_popular", "name"]
        unique_together = [
            ["autoservice", "name"]
        ]  # Уникальность названия в рамках автосервиса


class Order(models.Model):
    """Заказы клиентов"""

    STATUS_CHOICES = [
        ("pending", "Ожидает подтверждения"),
        ("confirmed", "Подтверждён"),
        ("in_progress", "В работе"),
        ("completed", "Выполнен"),
        ("cancelled", "Отменён"),
    ]

    # Основная информация
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Услуга",
    )
    autoservice = models.ForeignKey(
        AutoService,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Автосервис",
    )
    
    # Связь с пользователем (клиентом)
    client = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Клиент",
        help_text="Пользователь, который сделал заказ",
        null=True,
        blank=True
    )

    # Информация об автомобиле - может быть связана с сохраненным автомобилем
    car = models.ForeignKey(
        Car,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Автомобиль из профиля",
        help_text="Выберите из сохраненных автомобилей или оставьте пустым для ввода вручную"
    )
    
    # Данные автомобиля (заполняются автоматически из Car или вручную)
    car_brand = models.CharField(max_length=50, verbose_name="Марка автомобиля")
    car_model = models.CharField(max_length=50, verbose_name="Модель автомобиля")
    car_year = models.PositiveIntegerField(
        verbose_name="Год выпуска", help_text="Год выпуска автомобиля"
    )
    car_number = models.CharField(
        max_length=15,
        blank=True,
        verbose_name="Госномер",
        help_text="Государственный номер автомобиля (необязательно)",
    )

    # Детали заказа
    description = models.TextField(
        blank=True,
        verbose_name="Описание проблемы",
        help_text="Опишите проблему или особые пожелания",
    )
    preferred_date = models.DateField(
        verbose_name="Предпочтительная дата",
        help_text="Когда вам удобно привезти автомобиль",
    )
    preferred_time = models.TimeField(
        verbose_name="Предпочтительное время",
        help_text="Во сколько вам удобно приехать",
    )

    # Статус и метаданные
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Статус заказа",
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Итоговая цена",
        help_text="Окончательная стоимость (может отличаться от базовой цены услуги)",
    )
    estimated_duration = models.PositiveIntegerField(
        verbose_name="Оценочное время выполнения (мин)",
        help_text="Время выполнения в минутах",
    )

    # Системные поля
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата изменения")

    # Комментарии автосервиса
    admin_notes = models.TextField(
        blank=True,
        verbose_name="Комментарии автосервиса",
        help_text="Внутренние заметки для сотрудников",
    )

    def __str__(self):
        return f"Заказ #{self.id} - {self.get_client_name()} ({self.service.name})"

    def get_status_display_color(self):
        """Возвращает CSS класс для отображения статуса"""
        status_colors = {
            "pending": "warning",
            "confirmed": "info",
            "in_progress": "primary",
            "completed": "success",
            "cancelled": "danger",
        }
        return status_colors.get(self.status, "secondary")

    def get_car_info(self):
        """Возвращает информацию об автомобиле в удобном формате"""
        car_info = f"{self.car_brand} {self.car_model} ({self.car_year})"
        if self.car_number:
            car_info += f" - {self.car_number}"
        return car_info
    
    def get_client_name(self):
        """Возвращает имя клиента"""
        if not self.client:
            return "Неизвестный клиент"
        if self.client.first_name or self.client.last_name:
            return f"{self.client.first_name} {self.client.last_name}".strip()
        return self.client.username
    
    def get_client_phone(self):
        """Возвращает телефон клиента"""
        if not self.client:
            return "Не указан"
        return self.client.phone if self.client.phone else "Не указан"
    
    def get_client_email(self):
        """Возвращает email клиента"""
        if not self.client:
            return "Не указан"
        return self.client.email

    def save(self, *args, **kwargs):
        # Автоматически устанавливаем автосервис и базовые цены при создании
        if not self.pk:  # Только при создании
            self.autoservice = self.service.autoservice
            if not self.total_price:
                self.total_price = self.service.price
            if not self.estimated_duration:
                self.estimated_duration = self.service.duration
        
        # Если выбран сохраненный автомобиль, копируем его данные
        if self.car and not all([self.car_brand, self.car_model, self.car_year]):
            self.car_brand = self.car.brand
            self.car_model = self.car.model
            self.car_year = self.car.year
            if not self.car_number and self.car.number:
                self.car_number = self.car.number

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]


class Notification(models.Model):
    """Модель уведомлений для пользователей"""
    
    LEVEL_CHOICES = [
        ('info', 'Информация'),
        ('success', 'Успех'),
        ('warning', 'Предупреждение'),
        ('error', 'Ошибка'),
    ]
    
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Заголовок'
    )
    message = models.TextField(
        verbose_name='Сообщение'
    )
    level = models.CharField(
        max_length=10,
        choices=LEVEL_CHOICES,
        default='info',
        verbose_name='Уровень'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Прочитано'
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='Удалено'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата прочтения'
    )
    
    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'is_deleted']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f'{self.user.email}: {self.title}'
    
    def mark_as_read(self):
        """Отметить уведомление как прочитанное"""
        if not self.is_read:
            self.is_read = True
            from django.utils import timezone
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_deleted(self):
        """Отметить уведомление как удаленное"""
        self.is_deleted = True
        self.save(update_fields=['is_deleted'])
    
    @classmethod
    def create_notification(cls, user, title, message, level='info'):
        """Создать новое уведомление"""
        return cls.objects.create(
            user=user,
            title=title,
            message=message,
            level=level
        )
    
    @classmethod
    def get_unread_count(cls, user):
        """Получить количество непрочитанных уведомлений пользователя"""
        return cls.objects.filter(
            user=user,
            is_read=False,
            is_deleted=False
        ).count()
    
    @classmethod
    def get_user_notifications(cls, user, include_read=True, limit=None):
        """Получить уведомления пользователя"""
        queryset = cls.objects.filter(
            user=user,
            is_deleted=False
        )
        
        if not include_read:
            queryset = queryset.filter(is_read=False)
        
        if limit:
            queryset = queryset[:limit]
            
        return queryset
