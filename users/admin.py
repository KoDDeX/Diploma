from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from .models import User
from core.models import AutoService
from django import forms


class UserAdminForm(forms.ModelForm):
    """Кастомная форма для админки пользователя"""

    class Meta:
        model = User
        fields = "__all__"

    def clean(self):
        """Проверка: для менеджеров и админов сервис обязателен"""
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        autoservice = cleaned_data.get("autoservice")

        if role in ["autoservice_admin", "manager"] and not autoservice:
            raise ValidationError(
                "Для ролей 'Администратор автосервиса' и 'Менеджер' необходимо указать автосервис."
            )

        if role == "client":
            cleaned_data["autoservice"] = None

        return cleaned_data


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Админка для пользователей, доступная только для super_admin"""

    form = UserAdminForm
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "autoservice",
        "is_active",
    )
    list_filter = ("role", "is_active", "autoservice")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("email",)

    # ЭТОТ МЕТОД - ГЛАВНЫЙ. Он блокирует доступ всем, кроме super_admin.
    def has_view_permission(self, request, obj=None):
        """Разрешаем просмотр списка пользователей только для super_admin."""
        return (
            request.user.is_superuser
            or getattr(request.user, "role", None) == "super_admin"
        )

    def has_module_permission(self, request):
        """Только супер-админы видят модуль пользователей"""
        return request.user.is_superuser or getattr(request.user, "role", None) == "super_admin"

    def get_fieldsets(self, request, obj=None):
        """Настраиваем поля в зависимости от роли"""
        # Упрощаем, т.к. только super_admin видит эту страницу
        base_fields = (
            (None, {"fields": ("username", "password")}),
            (
                "Персональная информация",
                {
                    "fields": (
                        "first_name",
                        "last_name",
                        "email",
                        "avatar",
                        "birth_date",
                    )
                },
            ),
            ("Роль и Автосервис", {"fields": ("role", "autoservice")}),
            ("Важные даты", {"fields": ("last_login", "date_joined")}),
        )
        # Для super_admin всегда показываем все поля
        return base_fields + (
            (
                "Права доступа",
                {
                    "fields": (
                        "is_active",
                        "is_staff",
                        "is_superuser",
                        "groups",
                        "user_permissions",
                    )
                },
            ),
        )

    def get_readonly_fields(self, request, obj=None):
        """Ограничиваем редактирование полей"""
        # Только базовые поля, которые Django делает readonly по умолчанию
        return ["date_joined", "last_login"]
