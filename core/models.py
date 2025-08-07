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

    # Назначение мастера
    assigned_master = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
        verbose_name="Назначенный мастер",
        help_text="Мастер, назначенный на выполнение заказа",
        limit_choices_to={'role': 'master'}
    )
    
    # Предпочитаемый мастер (выбор клиента)
    preferred_master = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_orders",
        verbose_name="Предпочитаемый мастер",
        help_text="Мастер, которого предпочел клиент",
        limit_choices_to={'role': 'master'}
    )

    # Системные поля
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата изменения")
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата завершения",
        help_text="Дата и время завершения заказа"
    )

    # Комментарии автосервиса
    admin_notes = models.TextField(
        blank=True,
        verbose_name="Комментарии автосервиса",
        help_text="Внутренние заметки для сотрудников",
    )
    
    # Отзыв о заказе
    review_left = models.BooleanField(
        default=False,
        verbose_name="Отзыв оставлен",
        help_text="Отметка о том, что клиент оставил отзыв по данному заказу"
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


class WorkSchedule(models.Model):
    """Модель для графика работы мастеров"""
    
    SCHEDULE_TYPE_CHOICES = [
        ('weekly', 'Еженедельный'),
        ('monthly', 'Месячный'),
        ('custom', 'Индивидуальный'),
    ]
    
    # Основные поля
    master = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'master'},
        verbose_name='Мастер',
        help_text='Мастер, для которого создается график'
    )
    
    schedule_type = models.CharField(
        max_length=20,
        choices=SCHEDULE_TYPE_CHOICES,
        default='weekly',
        verbose_name='Тип графика'
    )
    
    # Период действия графика
    start_date = models.DateField(
        verbose_name='Дата начала действия',
        help_text='С какой даты действует график'
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата окончания действия',
        help_text='До какой даты действует график (пустое поле = бессрочно)'
    )
    
    # Для кастомного графика - дни недели через запятую (1,3,5 = Пн,Ср,Пт)
    custom_days = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Дни недели',
        help_text='Дни недели через запятую: 1-Пн, 2-Вт, 3-Ср, 4-Чт, 5-Пт, 6-Сб, 7-Вс'
    )
    
    # Рабочие часы
    start_time = models.TimeField(
        verbose_name='Время начала работы',
        help_text='Во сколько начинается рабочий день'
    )
    
    end_time = models.TimeField(
        verbose_name='Время окончания работы',
        help_text='Во сколько заканчивается рабочий день'
    )
    
    # Активность графика
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный график',
        help_text='Активные графики используются для расчета загрузки'
    )
    
    # Комментарии
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания',
        help_text='Дополнительная информация о графике'
    )
    
    # Системные поля
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')
    
    class Meta:
        verbose_name = 'График работы'
        verbose_name_plural = 'Графики работы'
        ordering = ['master__first_name', 'master__last_name', 'start_date']
        unique_together = ['master', 'schedule_type', 'start_date', 'custom_days']
    
    def __str__(self):
        master_name = self.master.get_full_name() or self.master.username
        return f"{master_name} - {self.get_schedule_type_display()} ({self.start_date})"
    
    def get_working_days(self):
        """Возвращает список рабочих дней недели"""
        if self.schedule_type == 'weekly':
            return [1, 2, 3, 4, 5]  # Пн-Пт по умолчанию
        elif self.schedule_type == 'custom' and self.custom_days:
            try:
                return [int(day.strip()) for day in self.custom_days.split(',')]
            except ValueError:
                return []
        else:
            return list(range(1, 8))  # Все дни недели
    
    def is_working_day(self, date):
        """Проверяет, является ли указанная дата рабочим днем"""
        if not self.is_active:
            return False
        
        # Проверяем период действия
        if date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False
        
        # Проверяем день недели (1=Понедельник, 7=Воскресенье)
        weekday = date.isoweekday()
        working_days = self.get_working_days()
        
        return weekday in working_days
    
    def is_working_at_time(self, datetime_obj):
        """Проверяет, работает ли мастер в указанную дату и время"""
        if not self.is_working_day(datetime_obj.date()):
            return False
        
        return self.start_time <= datetime_obj.time() <= self.end_time
    
    def get_conflicts(self):
        """Возвращает конфликтующие графики того же мастера"""
        conflicts = []
        
        # Ищем пересекающиеся по времени графики
        overlapping = WorkSchedule.objects.filter(
            master=self.master,
            is_active=True
        ).exclude(pk=self.pk)
        
        for schedule in overlapping:
            # Проверяем пересечение периодов
            if self._periods_overlap(schedule):
                # Проверяем пересечение дней недели
                if self._days_overlap(schedule):
                    # Проверяем пересечение времени
                    if self._time_overlap(schedule):
                        conflicts.append(schedule)
        
        return conflicts
    
    def _periods_overlap(self, other):
        """Проверяет пересечение периодов действия"""
        # Если у нас нет конечной даты, а у другого есть начальная
        if not self.end_date:
            return other.start_date >= self.start_date
        
        # Если у другого нет конечной даты
        if not other.end_date:
            return self.start_date <= other.start_date
        
        # Оба имеют конечные даты
        return not (self.end_date < other.start_date or other.end_date < self.start_date)
    
    def _days_overlap(self, other):
        """Проверяет пересечение рабочих дней"""
        our_days = set(self.get_working_days())
        other_days = set(other.get_working_days())
        return bool(our_days.intersection(other_days))
    
    def _time_overlap(self, other):
        """Проверяет пересечение времени работы"""
        return not (self.end_time <= other.start_time or other.end_time <= self.start_time)
    
    def clean(self):
        """Валидация модели"""
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        # Базовые проверки времени
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError('Время начала работы должно быть раньше времени окончания')
            
            # Проверяем разумность рабочего дня (не более 12 часов)
            from datetime import datetime, timedelta
            start_datetime = datetime.combine(datetime.today(), self.start_time)
            end_datetime = datetime.combine(datetime.today(), self.end_time)
            work_duration = (end_datetime - start_datetime).seconds / 3600
            
            if work_duration > 12:
                raise ValidationError('Рабочий день не может быть длиннее 12 часов')
            if work_duration < 1:
                raise ValidationError('Рабочий день должен быть не менее 1 часа')
        
        # Проверки дат
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError('Дата начала должна быть раньше даты окончания')
            
            # Максимальный период графика - 1 год
            if (self.end_date - self.start_date).days > 365:
                raise ValidationError('Максимальный период графика - 1 год')
        
        # Дата начала не может быть в прошлом (только для новых графиков)
        if not self.pk and self.start_date and self.start_date < timezone.now().date():
            raise ValidationError('Дата начала не может быть в прошлом')
        
        # Для кастомного графика проверяем дни недели
        if self.schedule_type == 'custom' and self.custom_days:
            try:
                days = [int(day.strip()) for day in self.custom_days.split(',')]
                if not all(1 <= day <= 7 for day in days):
                    raise ValidationError('Дни недели должны быть числами от 1 до 7')
                if not days:
                    raise ValidationError('Должен быть выбран хотя бы один рабочий день')
            except ValueError:
                raise ValidationError('Дни недели должны быть числами, разделенными запятыми')
        
        # Проверяем активность только одного графика на период
        if self.is_active and self.master_id:
            overlapping = WorkSchedule.objects.filter(
                master=self.master,
                is_active=True,
                start_date__lte=self.end_date if self.end_date else timezone.now().date() + timedelta(days=365),
                end_date__gte=self.start_date
            )
            
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            
            if overlapping.exists():
                conflicting_schedule = overlapping.first()
                raise ValidationError(
                    f'У мастера уже есть активный график на этот период: '
                    f'{conflicting_schedule.start_date.strftime("%d.%m.%Y")} - '
                    f'{conflicting_schedule.end_date.strftime("%d.%m.%Y") if conflicting_schedule.end_date else "бессрочно"}'
                )

    def save(self, *args, **kwargs):
        self.full_clean()  # Вызываем валидацию перед сохранением
        super().save(*args, **kwargs)


# Вспомогательные функции для работы с графиком
def get_master_schedule_for_date(master, date):
    """Получает активный график работы мастера на конкретную дату"""
    schedules = WorkSchedule.objects.filter(
        master=master,
        is_active=True,  # Только активные графики
        start_date__lte=date
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=date)
    )
    
    # Ищем график, который покрывает эту дату
    for schedule in schedules:
        if schedule.is_working_day(date):
            return schedule
    
    return None


def is_master_working_at_datetime(master, datetime_obj):
    """Проверяет, работает ли мастер в указанную дату и время"""
    schedule = get_master_schedule_for_date(master, datetime_obj.date())
    
    if not schedule:
        return False  # Если нет активного графика, мастер не работает
    
    return schedule.is_working_at_time(datetime_obj)


class Review(models.Model):
    """Модель отзывов с поддержкой разных типов объектов"""
    
    RATING_CHOICES = [
        (1, '⭐ Очень плохо'),
        (2, '⭐⭐ Плохо'),
        (3, '⭐⭐⭐ Нормально'),
        (4, '⭐⭐⭐⭐ Хорошо'),
        (5, '⭐⭐⭐⭐⭐ Отлично'),
    ]
    
    REVIEW_TYPE_CHOICES = [
        ('autoservice', 'Отзыв об автосервисе'),
        ('master', 'Отзыв о мастере'),
        ('manager', 'Отзыв о менеджере'),
        ('administrator', 'Отзыв об администраторе'),
        ('service', 'Отзыв об услуге'),
        ('client', 'Отзыв о клиенте'),
    ]
    
    # Автор отзыва
    author = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='authored_reviews',
        verbose_name='Автор отзыва'
    )
    
    # Тип отзыва
    review_type = models.CharField(
        max_length=20,
        choices=REVIEW_TYPE_CHOICES,
        verbose_name='Тип отзыва'
    )
    
    # Ссылки на объекты (только одно поле должно быть заполнено)
    autoservice = models.ForeignKey(
        'AutoService',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reviews',
        verbose_name='Автосервис'
    )
    
    reviewed_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='received_reviews',
        verbose_name='Пользователь (мастер/менеджер/админ/клиент)'
    )
    
    service = models.ForeignKey(
        'Service',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reviews',
        verbose_name='Услуга'
    )
    
    # Связь с заказом (для контекста)
    order = models.ForeignKey(
        'Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        verbose_name='Связанный заказ'
    )
    
    # Основные поля отзыва
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        verbose_name='Оценка'
    )
    
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Заголовок отзыва'
    )
    
    text = models.TextField(
        verbose_name='Текст отзыва'
    )
    
    # Плюсы и минусы (опционально)
    pros = models.TextField(
        blank=True,
        verbose_name='Плюсы',
        help_text='Что понравилось'
    )
    
    cons = models.TextField(
        blank=True,
        verbose_name='Минусы',
        help_text='Что не понравилось'
    )
    
    # Модерация
    is_approved = models.BooleanField(
        default=False,
        verbose_name='Одобрен'
    )
    
    is_rejected = models.BooleanField(
        default=False,
        verbose_name='Отклонён'
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата одобрения'
    )
    
    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата отклонения'
    )
    
    is_anonymous = models.BooleanField(
        default=False,
        verbose_name='Анонимный отзыв'
    )
    
    # Служебные поля
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    moderated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата модерации'
    )
    
    moderated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_reviews',
        verbose_name='Модератор'
    )
    
    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['review_type', 'is_approved']),
            models.Index(fields=['rating', 'created_at']),
            models.Index(fields=['autoservice', 'is_approved']),
            models.Index(fields=['reviewed_user', 'is_approved']),
        ]
    
    def __str__(self):
        target = self.get_review_target()
        return f'Отзыв от {self.author.get_full_name()} о {target} ({self.rating}/5)'
    
    def get_review_target(self):
        """Возвращает объект, о котором оставлен отзыв"""
        if self.autoservice:
            return f'автосервисе "{self.autoservice.name}"'
        elif self.reviewed_user:
            role_names = {
                'master': 'мастере',
                'manager': 'менеджере', 
                'autoservice_admin': 'администраторе',
                'client': 'клиенте'
            }
            role_name = role_names.get(self.reviewed_user.role, 'пользователе')
            return f'{role_name} {self.reviewed_user.get_full_name()}'
        elif self.service:
            return f'услуге "{self.service.name}"'
        return 'неизвестном объекте'
    
    def get_rating_stars(self):
        """Возвращает строку со звездами для отображения рейтинга"""
        full_stars = '⭐' * self.rating
        empty_stars = '☆' * (5 - self.rating)
        return full_stars + empty_stars
    
    def save(self, *args, **kwargs):
        # Автоматически генерируем заголовок, если он не задан
        if not self.title:
            self.title = self.generate_title()
        
        super().save(*args, **kwargs)
    
    def generate_title(self):
        """Автоматически генерирует заголовок отзыва на основе рейтинга и типа"""
        # Разные формы прилагательных для разных типов объектов
        rating_phrases = {
            'autoservice': {
                5: "Отличный",
                4: "Хороший", 
                3: "Обычный",
                2: "Не очень",
                1: "Плохой"
            },
            'master': {
                5: "Отличный",
                4: "Хороший", 
                3: "Обычный",
                2: "Не очень",
                1: "Плохой"
            },
            'manager': {
                5: "Отличный",
                4: "Хороший", 
                3: "Обычный",
                2: "Не очень",
                1: "Плохой"
            },
            'administrator': {
                5: "Отличный",
                4: "Хороший", 
                3: "Обычный",
                2: "Не очень",
                1: "Плохой"
            },
            'client': {
                5: "Отличный",
                4: "Хороший", 
                3: "Обычный",
                2: "Не очень",
                1: "Плохой"
            },
            'service': {
                5: "Отличная",
                4: "Хорошая", 
                3: "Обычная",
                2: "Не очень",
                1: "Плохая"
            }
        }
        
        type_names = {
            'autoservice': "автосервис",
            'master': "мастер", 
            'manager': "менеджер",
            'administrator': "администратор",
            'client': "клиент",
            'service': "услуга"
        }
        
        # Получаем правильную форму прилагательного для данного типа
        rating_words = rating_phrases.get(self.review_type, rating_phrases['autoservice'])
        rating_word = rating_words.get(self.rating, "")
        type_word = type_names.get(self.review_type, "объект")
        
        return f"{rating_word} {type_word}"


class ReviewReply(models.Model):
    """Ответы на отзывы от администрации автосервиса"""
    
    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name='reply',
        verbose_name='Отзыв'
    )
    
    author = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='review_replies',
        verbose_name='Автор ответа'
    )
    
    text = models.TextField(
        verbose_name='Текст ответа'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    class Meta:
        verbose_name = 'Ответ на отзыв'
        verbose_name_plural = 'Ответы на отзывы'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Ответ от {self.author.get_full_name()} на отзыв #{self.review.id}'
