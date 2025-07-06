from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Админка для кастомной модели пользователя."""

    # Поля, которые отображаются в списке пользователей
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")

    # Добавляем поле avatar в админку
    fieldsets = UserAdmin.fieldsets + (
        ("Дополнительная информация", {"fields": ("avatar", "birth_date")}),
    )

    # Поля для создания нового пользователя
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Дополнительная информация",
            {"fields": ("email", "first_name", "last_name", "avatar", "birth_date")},
        ),
    )
