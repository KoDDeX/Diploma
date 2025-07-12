from django.contrib import admin
from .models import Region, AutoService


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
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
    list_display = ("name", "region", "phone", "email", "is_active", "created_at")
    list_filter = ("region", "is_active", "created_at")
    search_fields = ("name", "address", "phone", "email")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("region__name", "name")

    fieldsets = (
        ("Основная информация", {"fields": ("name", "slug", "region", "is_active")}),
        ("Контактная информация", {"fields": ("address", "phone", "email")}),
        ("Дополнительно", {"fields": ("description", "image", "logo")}),
    )

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