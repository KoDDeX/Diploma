from django.db import models
from django.urls import reverse


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
