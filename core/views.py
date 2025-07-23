from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.db.models import Count
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from .models import Region, AutoService
from .forms import AutoServiceEditForm, AddManagerForm

User = get_user_model()


class LandingPageView(TemplateView):
    """Представление для главной страницы сайта."""

    template_name = "core/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Получаем все активные регионы
        all_regions = Region.objects.filter(is_active=True)

        # Получаем все активные автосервисы
        all_autoservices = AutoService.objects.filter(is_active=True).select_related(
            "region"
        )

        # Группируем автосервисы по регионам
        autoservices_by_region = {}
        regions_with_autoservices = []

        for autoservice in all_autoservices:
            region = autoservice.region
            if region not in autoservices_by_region:
                autoservices_by_region[region] = []
                regions_with_autoservices.append(region)
            autoservices_by_region[region].append(autoservice)

        context.update(
            {
                "title": "Выберите автосервис",
                "regions": regions_with_autoservices,
                "autoservices_by_region": autoservices_by_region,
            }
        )
        return context


def autoservice_detail_view(request, autoservice_slug):
    """Страница конкретного автосервиса"""
    autoservice = get_object_or_404(AutoService, slug=autoservice_slug)

    context = {
        "title": f"{autoservice.name} - {autoservice.region.name}",
        "autoservice": autoservice,
    }
    return render(request, "core/autoservice_detail.html", context)


def is_super_admin(user):
    """Проверка, является ли пользователь суперадминистратором"""
    return user.is_authenticated and user.role == "super_admin"


@login_required
@user_passes_test(is_super_admin)
def admin_panel_view(request):
    """Панель управления для суперадминистратора"""

    # Получаем фильтр из параметров GET
    filter_type = request.GET.get("filter", "all")

    # Базовый queryset с загрузкой связанных данных
    autoservices = AutoService.objects.select_related("region").prefetch_related(
        "user_set"
    )

    # Применяем фильтры
    if filter_type == "active":
        autoservices = autoservices.filter(is_active=True)
    elif filter_type == "inactive":
        autoservices = autoservices.filter(is_active=False)
    # Для 'all' не применяем дополнительных фильтров

    # Сортировка
    autoservices = autoservices.order_by("region__name", "name")

    # Добавляем информацию о администраторах и менеджерах для каждого автосервиса
    for autoservice in autoservices:
        # Получаем всех сотрудников автосервиса
        all_staff = autoservice.user_set.filter(is_active=True).exclude(
            role="super_admin"
        )

        # Разделяем на администраторов и менеджеров
        autoservice.admins = all_staff.filter(role="autoservice_admin")
        autoservice.managers = all_staff.filter(role="manager")
        autoservice.total_staff = all_staff.count()

    context = {
        "title": "Панель управления автосервисами",
        "autoservices": autoservices,
        "current_filter": filter_type,
        "filters": [
            ("all", "Все"),
            ("active", "Активные"),
            ("inactive", "Неактивные"),
        ],
    }

    return render(request, "core/admin_panel.html", context)


@login_required
@user_passes_test(is_super_admin)
@require_POST
def toggle_autoservice_status(request, autoservice_id):
    """AJAX view для изменения статуса автосервиса"""

    # Проверяем, что это AJAX запрос
    if not request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": False, "error": "Только AJAX запросы"})

    try:
        autoservice = get_object_or_404(AutoService, id=autoservice_id)
        autoservice.is_active = not autoservice.is_active
        autoservice.save()

        status_text = "активен" if autoservice.is_active else "неактивен"
        button_text = "Деактивировать" if autoservice.is_active else "Активировать"
        button_class = "btn-warning" if autoservice.is_active else "btn-success"

        return JsonResponse(
            {
                "success": True,
                "is_active": autoservice.is_active,
                "status_text": status_text,
                "button_text": button_text,
                "button_class": button_class,
                "message": f'Статус автосервиса "{autoservice.name}" изменён на "{status_text}"',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@user_passes_test(is_super_admin)
def get_users_for_manager(request, autoservice_id):
    """AJAX view для получения списка пользователей для назначения менеджером"""

    # Проверяем, что это AJAX запрос
    if not request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Если это не AJAX запрос, возвращаем JSON ошибку вместо перенаправления
        return JsonResponse({"success": False, "error": "Только AJAX запросы"})

    try:
        autoservice = get_object_or_404(AutoService, id=autoservice_id)

        # Получаем всех пользователей, отсортированных по фамилии и имени
        users = (
            User.objects.filter(is_active=True)
            .exclude(role="super_admin")  # Исключаем суперадминов
            .order_by("last_name", "first_name", "username")
        )

        users_data = []
        for user in users:
            # Определяем отображаемое имя
            if user.last_name or user.first_name:
                display_name = f"{user.last_name} {user.first_name}".strip()
            else:
                display_name = user.username

            users_data.append(
                {
                    "id": user.id,
                    "display_name": display_name,
                    "username": user.username,
                    "email": user.email,
                    "role": user.get_role_display(),
                    "is_manager": (autoservice.user_set.filter(id=user.id).exists()),
                }
            )

        return JsonResponse(
            {"success": True, "users": users_data, "autoservice_name": autoservice.name}
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@user_passes_test(is_super_admin)
@require_POST
def assign_manager(request, autoservice_id, user_id):
    """AJAX view для назначения менеджера автосервиса"""

    # Проверяем, что это AJAX запрос
    if not request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": False, "error": "Только AJAX запросы"})

    try:
        autoservice = get_object_or_404(AutoService, id=autoservice_id)
        user = get_object_or_404(User, id=user_id)

        # Проверяем, не является ли пользователь уже сотрудником этого автосервиса
        if user.autoservice == autoservice:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Пользователь уже является сотрудником данного автосервиса",
                }
            )

        # Проверяем, не работает ли пользователь в другом автосервисе
        if user.autoservice and user.autoservice != autoservice:
            return JsonResponse(
                {
                    "success": False,
                    "error": f'Пользователь уже работает в автосервисе "{user.autoservice.name}"',
                }
            )

        # Назначаем пользователя менеджером
        user.autoservice = autoservice
        user.role = "manager"  # По умолчанию назначаем роль менеджера
        user.save()

        # Определяем отображаемое имя
        if user.last_name or user.first_name:
            display_name = f"{user.last_name} {user.first_name}".strip()
        else:
            display_name = user.username

        return JsonResponse(
            {
                "success": True,
                "message": f'Пользователь "{display_name}" назначен сотрудником автосервиса "{autoservice.name}"',
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# =============================================================================
# ПАНЕЛЬ АДМИНИСТРАТОРА АВТОСЕРВИСА
# =============================================================================


def is_autoservice_admin(user):
    """Проверка, является ли пользователь администратором автосервиса"""
    return (
        user.is_authenticated
        and user.role == "autoservice_admin"
        and user.autoservice is not None
    )


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_admin_dashboard(request):
    """Главная панель администратора автосервиса"""
    autoservice = request.user.autoservice

    # Получаем всех менеджеров данного автосервиса
    all_managers = User.objects.filter(autoservice=autoservice, is_active=True).exclude(
        role="super_admin"
    )

    # Получаем только менеджеров (исключая администраторов автосервиса)
    managers = all_managers.filter(role="manager").order_by(
        "last_name", "first_name", "username"
    )

    # Статистика
    total_managers = all_managers.count()
    active_managers = all_managers.filter(is_active=True).count()
    manager_count = managers.count()
    admin_count = all_managers.filter(role="autoservice_admin").count()

    context = {
        "title": f"Панель управления - {autoservice.name}",
        "autoservice": autoservice,
        "managers": managers,
        "total_managers": total_managers,
        "active_managers": active_managers,
        "manager_count": manager_count,
        "admin_count": admin_count,
    }
    return render(request, "core/autoservice_admin/dashboard.html", context)


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_edit_profile(request):
    """Редактирование профиля автосервиса"""
    autoservice = request.user.autoservice

    if request.method == "POST":
        form = AutoServiceEditForm(request.POST, instance=autoservice)
        if form.is_valid():
            form.save()
            messages.success(request, "Информация об автосервисе успешно обновлена!")
            return redirect("core:autoservice_admin_dashboard")
    else:
        form = AutoServiceEditForm(instance=autoservice)

    context = {
        "title": f"Редактирование - {autoservice.name}",
        "autoservice": autoservice,
        "form": form,
    }
    return render(request, "core/autoservice_admin/edit_profile.html", context)


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_managers_list(request):
    """Список менеджеров автосервиса"""
    autoservice = request.user.autoservice

    # Получаем всех сотрудников автосервиса
    all_managers = User.objects.filter(autoservice=autoservice, is_active=True).exclude(
        role="super_admin"
    )

    managers = all_managers.order_by("last_name", "first_name", "username")

    # Статистика для шаблона
    total_managers = all_managers.count()
    active_managers = all_managers.filter(is_active=True).count()
    manager_count = all_managers.filter(role="manager").count()
    admin_count = all_managers.filter(role="autoservice_admin").count()

    context = {
        "title": f"Менеджеры - {autoservice.name}",
        "autoservice": autoservice,
        "managers": managers,
        "total_managers": total_managers,
        "active_managers": active_managers,
        "manager_count": manager_count,
        "admin_count": admin_count,
    }
    return render(request, "core/autoservice_admin/managers_list.html", context)


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_add_manager(request):
    """Добавление менеджера в автосервис"""
    autoservice = request.user.autoservice

    if request.method == "POST":
        form = AddManagerForm(request.POST, autoservice=autoservice)
        if form.is_valid():
            user = form.get_user()
            role = form.cleaned_data["role"]

            if user:
                # Назначаем пользователя сотрудником автосервиса
                user.autoservice = autoservice
                user.role = role
                user.save()

                display_name = (
                    f"{user.last_name} {user.first_name}".strip()
                    if (user.last_name or user.first_name)
                    else user.username
                )
                role_display = (
                    "администратором" if role == "autoservice_admin" else "менеджером"
                )
                messages.success(
                    request,
                    f'Пользователь "{display_name}" назначен {role_display} автосервиса',
                )
                return redirect("core:autoservice_managers_list")
    else:
        form = AddManagerForm(autoservice=autoservice)

    context = {
        "title": f"Добавить сотрудника - {autoservice.name}",
        "autoservice": autoservice,
        "form": form,
    }
    return render(request, "core/autoservice_admin/add_manager.html", context)


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def autoservice_remove_manager(request, user_id):
    """Удаление менеджера из автосервиса"""
    autoservice = request.user.autoservice

    try:
        user = get_object_or_404(
            User, id=user_id, autoservice=autoservice, role="manager"
        )

        display_name = (
            f"{user.last_name} {user.first_name}".strip()
            if (user.last_name or user.first_name)
            else user.username
        )

        # Убираем пользователя из автосервиса
        user.autoservice = None
        user.role = "client"  # Возвращаем роль клиента
        user.save()

        messages.success(request, f'Менеджер "{display_name}" удален из автосервиса')

    except Exception as e:
        messages.error(request, f"Ошибка при удалении менеджера: {str(e)}")

    return redirect("core:autoservice_managers_list")
