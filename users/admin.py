from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

# # В админке или через код
# from django.contrib.auth.models import Group, Permission

# # Группа "Менеджеры"
# managers_group = Group.objects.create(name='Менеджеры')
# managers_group.permissions.add(
#     Permission.objects.get(codename='change_user'),
#     Permission.objects.get(codename='view_user'),
# )

# # Назначить пользователю
# user.groups.add(managers_group)
# user.is_staff = True  # Для доступа в админку

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
