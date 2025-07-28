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
        
        prices = services.values_list('price', flat=True)
        return min(prices), max(prices)

    def get_duration_range(self):
        """Возвращает диапазон времени на основе реальных услуг автосервисов"""
        services = self.autoservice_services.filter(is_active=True)
        if not services.exists():
            return None, None
        
        durations = services.values_list('duration', flat=True)
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
