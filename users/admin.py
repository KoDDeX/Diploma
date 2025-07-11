from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from .models import User, Region, AutoService
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


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    """Админка для регионов - только для суперадминов"""

    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_active",)

    def has_view_permission(self, request, obj=None):
        """Только суперадмины видят модель Регионы"""
        return (
            request.user.is_superuser
            or getattr(request.user, "role", None) == "super_admin"
        )

    def has_module_permission(self, request):
        """Кто видит модуль на главной странице админки"""
        return (
            request.user.is_superuser
            or getattr(request.user, "role", None) == "super_admin"
        )


@admin.register(AutoService)
class AutoServiceAdmin(admin.ModelAdmin):
    """Админка для автосервисов"""

    list_display = ("name", "region", "phone", "email", "is_active", "created_at")
    list_filter = ("region", "is_active", "created_at")
    search_fields = ("name", "phone", "email", "address")
    prepopulated_fields = {"slug": ("name",)}

    def get_prepopulated_fields(self, request, obj=None):
        """Отключаем автозаполнение slug, если поле только для чтения."""
        if "slug" in self.get_readonly_fields(request, obj):
            return {}
        return super().get_prepopulated_fields(request, obj)

    def has_module_permission(self, request):
        """
        Разрешаем доступ к модулю, если пользователь может видеть
        хотя бы одну модель внутри него.
        """
        return request.user.is_superuser or getattr(request.user, "role", None) in [
            "super_admin",
            "autoservice_admin",
            "manager",
        ]

    def get_queryset(self, request):
        """Показываем только нужные автосервисы"""
        queryset = super().get_queryset(request)
        user = request.user

        if user.is_superuser or getattr(user, "role", None) == "super_admin":
            return queryset

        # Для админов и менеджеров показываем только их автосервис
        if getattr(user, "role", None) in ["autoservice_admin", "manager"]:
            if hasattr(user, "autoservice") and user.autoservice:
                return queryset.filter(pk=user.autoservice.pk)

        return queryset.none()

    def has_view_permission(self, request, obj=None):
        """Разрешаем просмотр админу и менеджеру своего автосервиса."""
        user = request.user
        return (
            user.is_superuser
            or getattr(user, "role", None) == "super_admin"
            or getattr(user, "role", None) in ["autoservice_admin", "manager"]
        )

    def has_add_permission(self, request):
        """Только суперадмины могут добавлять автосервисы"""
        return (
            request.user.is_superuser
            or getattr(request.user, "role", None) == "super_admin"
        )

    def has_delete_permission(self, request, obj=None):
        """Только суперадмины могут удалять автосервисы"""
        return (
            request.user.is_superuser
            or getattr(request.user, "role", None) == "super_admin"
        )

    def has_change_permission(self, request, obj=None):
        """Администратор автосервиса может редактировать только свой."""
        user = request.user
        if user.is_superuser or getattr(user, "role", None) == "super_admin":
            return True

        if getattr(user, "role", None) == "autoservice_admin":
            # Если obj не None, проверяем, что это его сервис.
            # Если obj is None (страница списка), разрешаем доступ.
            # get_queryset позаботится о фильтрации.
            if obj:
                return hasattr(user, "autoservice") and obj == user.autoservice
            return True  # Разрешаем доступ к списку изменений

        return False

    def get_readonly_fields(self, request, obj=None):
        """Ограничиваем редактирование для администраторов автосервисов"""
        readonly_fields = []
        user_role = getattr(request.user, "role", None)

        if user_role == "autoservice_admin":
            # Администратор автосервиса не может менять ключевые поля
            readonly_fields = ["region", "slug", "is_active", "created_at"]
        elif user_role == "manager":
            # Менеджер может только просматривать
            readonly_fields = [
                "name",
                "region",
                "slug",
                "address",
                "phone",
                "email",
                "description",
                "logo",
                "is_active",
                "created_at",
            ]

        return readonly_fields


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
