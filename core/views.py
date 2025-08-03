from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import PermissionDenied
from datetime import timedelta
import json
from .models import Region, AutoService, Service, Order, Car, Notification, WorkSchedule, get_master_schedule_for_date, is_master_working_at_datetime
from .forms import (
    AutoServiceEditForm,
    AddManagerForm,
    AutoServiceRegistrationForm,
    ServiceCreateForm,
    OrderCreateForm,
    CarForm,
)

User = get_user_model()


# ============== HELPER ФУНКЦИИ ДЛЯ УВЕДОМЛЕНИЙ ==============

def add_notification(user, title, message, level='info'):
    """
    Создать уведомление для пользователя.
    
    Args:
        user: Пользователь для которого создается уведомление
        title: Заголовок уведомления
        message: Текст уведомления
        level: Уровень ('info', 'success', 'warning', 'error')
    """
    if user and user.is_authenticated:
        return Notification.create_notification(
            user=user,
            title=title,
            message=message,
            level=level
        )
    return None


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

    # Получаем активные услуги автосервиса
    services = autoservice.services.filter(is_active=True).order_by(
        "-is_popular", "name"
    )
    
    # Получаем последние отзывы об автосервисе (максимум 6 для отображения)
    recent_reviews = Review.objects.filter(
        autoservice=autoservice,
        is_approved=True
    ).select_related('author').order_by('-created_at')[:6]
    
    # Общая статистика отзывов
    total_reviews = Review.objects.filter(
        autoservice=autoservice,
        is_approved=True
    ).count()
    
    avg_rating = 0
    if total_reviews > 0:
        all_reviews = Review.objects.filter(
            autoservice=autoservice,
            is_approved=True
        )
        avg_rating = round(sum(review.rating for review in all_reviews) / total_reviews, 1)

    context = {
        "title": f"{autoservice.name} - {autoservice.region.name}",
        "autoservice": autoservice,
        "services": services,
        "recent_reviews": recent_reviews,
        "total_reviews": total_reviews,
        "avg_rating": avg_rating,
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
        # Получаем всех пользователей автосервиса (включая деактивированных)
        all_users = autoservice.user_set.filter(is_active=True).exclude(
            role="super_admin"
        )

        # Разделяем пользователей по ролям, учитывая previous_role для клиентов
        admins = []
        managers = []

        for user in all_users:
            # Определяем эффективную роль пользователя
            if user.role in ["autoservice_admin", "manager"]:
                # Активная роль
                effective_role = user.role
            elif user.role == "client" and user.previous_role in [
                "autoservice_admin",
                "manager",
            ]:
                # Клиент с сохраненной ролью (деактивированный сотрудник)
                effective_role = user.previous_role
            else:
                # Обычный клиент
                continue

            # Добавляем флаг деактивации для отображения
            user.is_deactivated = (
                user.role == "client" and user.previous_role is not None
            )

            if effective_role == "autoservice_admin":
                admins.append(user)
            elif effective_role == "manager":
                managers.append(user)

        autoservice.admins = admins
        autoservice.managers = managers
        autoservice.total_staff = len(admins) + len(managers)

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
        old_status = autoservice.is_active
        autoservice.is_active = not autoservice.is_active
        autoservice.save()

        # Управляем ролями пользователей при изменении статуса автосервиса
        if autoservice.is_active and not old_status:
            # Автосервис активируется - восстанавливаем роли
            activated_users = activate_autoservice_users(autoservice)
            
            # Уведомляем администратора автосервиса об активации
            autoservice_admin = autoservice.user_set.filter(
                role='autoservice_admin'
            ).first()
            if autoservice_admin:
                add_notification(
                    user=autoservice_admin,
                    title="Автосервис активирован",
                    message=f"Ваш автосервис '{autoservice.name}' был активирован администратором системы. Теперь вы можете полноценно управлять автосервисом.",
                    level="success"
                )
            
            if activated_users > 0:
                messages.success(
                    request,
                    f'Автосервис "{autoservice.name}" активирован! '
                    f"Восстановлены роли для {activated_users} пользователей.",
                )
            else:
                messages.success(
                    request, f'Автосервис "{autoservice.name}" активирован!'
                )
        elif not autoservice.is_active and old_status:
            # Автосервис деактивируется - сохраняем роли и переводим в клиенты
            deactivated_users = deactivate_autoservice_users(autoservice)
            
            # Уведомляем администратора автосервиса о деактивации
            autoservice_admin = autoservice.user_set.filter(
                role='autoservice_admin'
            ).first()
            if autoservice_admin:
                add_notification(
                    user=autoservice_admin,
                    title="Автосервис деактивирован",
                    message=f"Ваш автосервис '{autoservice.name}' был временно деактивирован администратором системы. Обратитесь к администратору для получения информации.",
                    level="warning"
                )
            
            if deactivated_users > 0:
                messages.info(
                    request,
                    f'Автосервис "{autoservice.name}" деактивирован! '
                    f"Роли сохранены для {deactivated_users} пользователей.",
                )
            else:
                messages.info(
                    request, f'Автосервис "{autoservice.name}" деактивирован!'
                )

        return JsonResponse(
            {
                "success": True,
                "reload_page": True,  # Указываем, что нужно перезагрузить страницу
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

        # Назначаем пользователя сотрудником автосервиса
        user.autoservice = autoservice

        # Если автосервис активен, назначаем роль менеджера сразу
        if autoservice.is_active:
            user.role = "manager"
            # Создаем уведомление о назначении
            add_notification(
                user=user,
                title="Назначение менеджером",
                message=f"Вы назначены менеджером автосервиса '{autoservice.name}' администратором системы. Добро пожаловать в команду!",
                level="success"
            )
        else:
            # Если автосервис неактивен, оставляем пользователя клиентом
            # Роль будет назначена администратором автосервиса позже
            add_notification(
                user=user,
                title="Добавление к автосервису",
                message=f"Вы добавлены к автосервису '{autoservice.name}'. Роль менеджера будет назначена при активации автосервиса.",
                level="info"
            )
            pass

        user.save()

        # Определяем отображаемое имя
        if user.last_name or user.first_name:
            display_name = f"{user.last_name} {user.first_name}".strip()
        else:
            display_name = user.username

        # Добавляем сообщение через Django messages
        if autoservice.is_active:
            messages.success(
                request,
                f'Пользователь "{display_name}" назначен менеджером автосервиса "{autoservice.name}"',
            )
        else:
            messages.info(
                request,
                f'Пользователь "{display_name}" добавлен к автосервису "{autoservice.name}". '
                f"Роль менеджера будет назначена при активации автосервиса.",
            )

        return JsonResponse(
            {
                "success": True,
                "reload_page": True,  # Указываем, что нужно перезагрузить страницу
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# =============================================================================
# ПАНЕЛЬ АДМИНИСТРАТОРА АВТОСЕРВИСА
# =============================================================================


def is_autoservice_admin(user):
    """Проверка, является ли пользователь администратором автосервиса, менеджером или мастером"""
    return (
        user.is_authenticated
        and user.role in ["autoservice_admin", "manager", "master"]
        and user.autoservice is not None
        and user.autoservice.is_active  # Добавляем проверку активности автосервиса
    )


def can_manage_users(user):
    """Проверка, может ли пользователь управлять другими пользователями"""
    return (
        user.is_authenticated
        and user.role in ["autoservice_admin", "manager"]
        and user.autoservice is not None
        and user.autoservice.is_active
    )


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_admin_dashboard(request):
    """Главная панель администратора автосервиса"""
    autoservice = request.user.autoservice
    
    # Получаем роли, которыми может управлять текущий пользователь
    manageable_roles = request.user.can_manage_users()

    # Получаем всех сотрудников, которыми может управлять пользователь
    all_staff = User.objects.filter(
        autoservice=autoservice, 
        role__in=manageable_roles,
        is_active=True
    ).exclude(role="super_admin")

    # Статистика по ролям
    stats = {}
    total_staff = 0
    
    for role_key, role_name in User.ROLE_CHOICES:
        if role_key in manageable_roles:
            count = all_staff.filter(role=role_key).count()
            stats[role_key] = {
                'name': role_name,
                'count': count
            }
            total_staff += count

    context = {
        "title": f"Панель управления - {autoservice.name}",
        "autoservice": autoservice,
        "total_staff": total_staff,
        "stats": stats,
        "manageable_roles": manageable_roles,
        "user_role": request.user.role,
        # Для обратной совместимости со старыми шаблонами
        "total_managers": total_staff,
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
@user_passes_test(can_manage_users)
def autoservice_managers_list(request):
    """Список сотрудников автосервиса"""
    autoservice = request.user.autoservice
    
    # Получаем роли, которыми может управлять текущий пользователь
    manageable_roles = request.user.can_manage_users()
    
    # Получаем сотрудников, которыми может управлять текущий пользователь
    staff = (
        User.objects.filter(
            autoservice=autoservice, 
            role__in=manageable_roles,
            is_active=True
        )
        .exclude(role="super_admin")
        .order_by("role", "last_name", "first_name", "username")
    )

    # Фильтрация по роли
    role_filter = request.GET.get('role')
    if role_filter and role_filter in manageable_roles:
        staff = staff.filter(role=role_filter)

    # Статистика для шаблона
    total_staff = staff.count()
    
    # Статистика по ролям
    stats = {}
    for role_key, role_name in User.ROLE_CHOICES:
        if role_key in manageable_roles:
            count = staff.filter(role=role_key).count()
            stats[role_key] = {
                'name': role_name,
                'count': count
            }

    context = {
        "title": f"Сотрудники - {autoservice.name}",
        "autoservice": autoservice,
        "staff": staff,
        "manageable_roles": manageable_roles,
        "role_choices": User.ROLE_CHOICES,
        "current_role_filter": role_filter,
        "total_staff": total_staff,
        "stats": stats,
        "user_role": request.user.role,
    }
    return render(request, "core/autoservice_admin/managers_list.html", context)


@login_required
@user_passes_test(can_manage_users)
def autoservice_add_manager(request):
    """Добавление сотрудника в автосервис (менеджера или мастера)"""
    autoservice = request.user.autoservice

    if request.method == "POST":
        form = AddManagerForm(request.POST, autoservice=autoservice, current_user=request.user)
        if form.is_valid():
            user = form.get_user()
            role = form.cleaned_data["role"]

            if user:
                # Проверяем права на назначение этой роли
                if role not in request.user.can_manage_users():
                    messages.error(request, "У вас нет прав для назначения этой роли")
                    return redirect("core:autoservice_managers_list")

                # Назначаем пользователя сотрудником автосервиса
                user.autoservice = autoservice
                user.role = role
                user.save()

                display_name = (
                    f"{user.last_name} {user.first_name}".strip()
                    if (user.last_name or user.first_name)
                    else user.username
                )
                
                role_display_map = {
                    "autoservice_admin": "администратором",
                    "manager": "менеджером", 
                    "master": "мастером"
                }
                role_display = role_display_map.get(role, role)
                
                # Создаем уведомление для назначенного пользователя
                add_notification(
                    user=user,
                    title="Назначение в автосервис",
                    message=f"Вы назначены {role_display} автосервиса '{autoservice.name}'. Добро пожаловать в команду!",
                    level="success"
                )
                
                messages.success(
                    request,
                    f'Пользователь "{display_name}" назначен {role_display} автосервиса',
                )
                return redirect("core:autoservice_managers_list")
    else:
        form = AddManagerForm(autoservice=autoservice, current_user=request.user)

    context = {
        "title": f"Добавить сотрудника - {autoservice.name}",
        "autoservice": autoservice,
        "form": form,
    }
    return render(request, "core/autoservice_admin/add_manager.html", context)


@login_required
@user_passes_test(can_manage_users)
@require_POST
def autoservice_remove_manager(request, user_id):
    """Удаление сотрудника из автосервиса"""
    autoservice = request.user.autoservice
    manageable_roles = request.user.can_manage_users()

    try:
        user = get_object_or_404(
            User, 
            id=user_id, 
            autoservice=autoservice, 
            role__in=manageable_roles
        )

        # Проверяем права на удаление этого пользователя
        if not request.user.can_manage_user(user):
            messages.error(request, "У вас нет прав для удаления этого сотрудника")
            return redirect("core:autoservice_managers_list")

        display_name = (
            f"{user.last_name} {user.first_name}".strip()
            if (user.last_name or user.first_name)
            else user.username
        )

        role_display = user.get_role_display()

        # Создаем уведомление для удаляемого сотрудника
        add_notification(
            user=user,
            title="Удаление из автосервиса",
            message=f"Вы были удалены из автосервиса '{autoservice.name}'. Ваша роль изменена на 'Клиент'.",
            level="info"
        )

        # Убираем пользователя из автосервиса
        user.autoservice = None
        user.role = "client"  # Возвращаем роль клиента
        user.save()

        messages.success(request, f'{role_display} "{display_name}" удален из автосервиса')

    except Exception as e:
        messages.error(request, f"Ошибка при удалении сотрудника: {str(e)}")

    return redirect("core:autoservice_managers_list")


def activate_autoservice_users(autoservice):
    """Активирует пользователей автосервиса, восстанавливая их роли"""
    # Получаем всех пользователей, привязанных к автосервису, у которых есть сохраненная роль
    users = User.objects.filter(autoservice=autoservice, previous_role__isnull=False)

    activated_count = 0
    for user in users:
        # Создаем уведомление об активации автосервиса
        add_notification(
            user=user,
            title="Автосервис активирован",
            message=f"Ваш автосервис '{autoservice.name}' был активирован администратором. Ваша роль '{user.get_role_display()}' восстановлена.",
            level="success"
        )
        
        # Восстанавливаем роль из previous_role
        user.role = user.previous_role
        user.previous_role = None  # Очищаем поле предыдущей роли
        user.save()
        activated_count += 1

    return activated_count


def deactivate_autoservice_users(autoservice):
    """Деактивирует пользователей автосервиса, сохраняя их роли"""
    # Получаем всех пользователей автосервиса (кроме суперадминов и уже клиентов)
    users = User.objects.filter(autoservice=autoservice).exclude(
        role__in=["super_admin", "client"]
    )

    deactivated_count = 0
    for user in users:
        # Создаем уведомление о деактивации автосервиса
        add_notification(
            user=user,
            title="Автосервис деактивирован",
            message=f"Ваш автосервис '{autoservice.name}' был временно деактивирован администратором. Обратитесь к администратору для получения дополнительной информации.",
            level="warning"
        )
        
        # Сохраняем текущую роль в поле previous_role
        user.previous_role = user.role
        # Переводим в клиенты
        user.role = "client"
        user.save()
        deactivated_count += 1

    return deactivated_count


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_service_create(request):
    """Создание новой услуги администратором автосервиса"""
    autoservice = request.user.autoservice

    if request.method == "POST":
        form = ServiceCreateForm(request.POST, request.FILES, autoservice=autoservice)
        if form.is_valid():
            service = form.save()
            
            # Создаем уведомление для администратора автосервиса
            add_notification(
                user=request.user,
                title="Услуга создана",
                message=f"Услуга '{service.name}' успешно создана в автосервисе '{autoservice.name}'. Цена: {service.price} руб.",
                level="success"
            )
            
            # Уведомляем менеджеров автосервиса о новой услуге
            managers = autoservice.user_set.filter(role='manager', is_active=True)
            for manager in managers:
                add_notification(
                    user=manager,
                    title="Новая услуга добавлена",
                    message=f"В автосервисе '{autoservice.name}' добавлена новая услуга '{service.name}' (цена: {service.price} руб.).",
                    level="info"
                )
            
            messages.success(request, f'Услуга "{service.name}" успешно создана!')
            return redirect("core:autoservice_services_list")
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = ServiceCreateForm(autoservice=autoservice)

    context = {
        "title": f"Создание услуги - {autoservice.name}",
        "autoservice": autoservice,
        "form": form,
    }
    return render(request, "core/autoservice_admin/service_create.html", context)


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_services_list(request):
    """Управление услугами автосервиса"""
    autoservice = request.user.autoservice

    # Получаем все услуги автосервиса
    services = (
        Service.objects.filter(autoservice=autoservice)
        .select_related("standard_service", "standard_service__category")
        .order_by("-is_popular", "standard_service__category__name", "name")
    )

    # Фильтрация по категориям
    category_filter = request.GET.get("category")
    if category_filter:
        services = services.filter(standard_service__category__slug=category_filter)

    # Фильтрация по статусу
    status_filter = request.GET.get("status")
    if status_filter == "active":
        services = services.filter(is_active=True)
    elif status_filter == "inactive":
        services = services.filter(is_active=False)
    elif status_filter == "popular":
        services = services.filter(is_popular=True)

    # Поиск по названию
    search_query = request.GET.get("search")
    if search_query:
        services = services.filter(name__icontains=search_query)

    # Статистика
    total_services = Service.objects.filter(autoservice=autoservice).count()
    active_services = Service.objects.filter(
        autoservice=autoservice, is_active=True
    ).count()
    popular_services = Service.objects.filter(
        autoservice=autoservice, is_popular=True
    ).count()

    # Получаем категории для фильтра (только те, у которых есть услуги в данном автосервисе)
    from core.models import ServiceCategory

    categories = (
        ServiceCategory.objects.filter(
            standard_services__autoservice_services__autoservice=autoservice
        )
        .distinct()
        .order_by("name")
    )

    context = {
        "title": f"Управление услугами - {autoservice.name}",
        "autoservice": autoservice,
        "services": services,
        "categories": categories,
        "total_services": total_services,
        "active_services": active_services,
        "popular_services": popular_services,
        "current_category": category_filter,
        "current_status": status_filter,
        "search_query": search_query or "",
    }
    return render(request, "core/autoservice_admin/services_list.html", context)


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_service_edit(request, service_id):
    """Редактирование услуги администратором автосервиса"""
    autoservice = request.user.autoservice
    service = get_object_or_404(Service, id=service_id, autoservice=autoservice)

    if request.method == "POST":
        form = ServiceCreateForm(
            request.POST, request.FILES, instance=service, autoservice=autoservice
        )
        if form.is_valid():
            old_price = service.price
            service = form.save()
            
            # Создаем уведомление об изменении услуги
            price_change = ""
            if old_price != service.price:
                price_change = f" Цена изменена с {old_price} на {service.price} руб."
            
            add_notification(
                user=request.user,
                title="Услуга обновлена",
                message=f"Услуга '{service.name}' в автосервисе '{autoservice.name}' успешно обновлена.{price_change}",
                level="success"
            )
            
            # Если цена изменилась, уведомляем менеджеров
            if old_price != service.price:
                managers = autoservice.user_set.filter(role='manager', is_active=True)
                for manager in managers:
                    add_notification(
                        user=manager,
                        title="Изменена цена услуги",
                        message=f"Цена услуги '{service.name}' изменена с {old_price} на {service.price} руб.",
                        level="info"
                    )
            
            messages.success(request, f'Услуга "{service.name}" успешно обновлена!')
            return redirect("core:autoservice_services_list")
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = ServiceCreateForm(instance=service, autoservice=autoservice)

    context = {
        "title": f"Редактирование услуги - {autoservice.name}",
        "autoservice": autoservice,
        "service": service,
        "form": form,
        "is_edit": True,
    }
    return render(request, "core/autoservice_admin/service_create.html", context)


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def autoservice_service_toggle(request, service_id):
    """Переключение активности услуги"""
    autoservice = request.user.autoservice
    service = get_object_or_404(Service, id=service_id, autoservice=autoservice)

    service.is_active = not service.is_active
    service.save()

    status = "активирована" if service.is_active else "деактивирована"
    
    # Создаем уведомление об изменении статуса услуги
    add_notification(
        user=request.user,
        title=f"Услуга {status}",
        message=f"Услуга '{service.name}' в автосервисе '{autoservice.name}' {status}.",
        level="info"
    )
    
    # Уведомляем менеджеров об изменении статуса услуги
    managers = autoservice.user_set.filter(role='manager', is_active=True)
    for manager in managers:
        add_notification(
            user=manager,
            title=f"Услуга {status}",
            message=f"Услуга '{service.name}' {status} администратором.",
            level="info"
        )

    messages.success(request, f'Услуга "{service.name}" {status}.')

    return redirect("core:autoservice_services_list")


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def autoservice_service_delete(request, service_id):
    """Удаление услуги"""
    autoservice = request.user.autoservice
    service = get_object_or_404(Service, id=service_id, autoservice=autoservice)

    service_name = service.name
    service_price = service.price
    
    # Создаем уведомление об удалении услуги
    add_notification(
        user=request.user,
        title="Услуга удалена",
        message=f"Услуга '{service_name}' (цена: {service_price} руб.) удалена из автосервиса '{autoservice.name}'.",
        level="warning"
    )
    
    # Уведомляем менеджеров об удалении услуги
    managers = autoservice.user_set.filter(role='manager', is_active=True)
    for manager in managers:
        add_notification(
            user=manager,
            title="Услуга удалена",
            message=f"Услуга '{service_name}' удалена из автосервиса администратором.",
            level="warning"
        )
    
    service.delete()

    messages.success(request, f'Услуга "{service_name}" удалена.')
    return redirect("core:autoservice_services_list")


@login_required
def autoservice_register_view(request):
    """Представление для регистрации нового автосервиса"""

    # Проверяем, что пользователь уже не является администратором автосервиса
    # Пользователь может иметь несколько автосервисов! Такое возможно!
    # if request.user.autoservice is not None:
    #     messages.warning(request, "Вы уже являетесь администратором автосервиса")
    #     return redirect("core:landing")

    # Проверяем, что пользователь не является суперадминистратором
    # А я что не знаю что мне ненадо регистрировать автосервис?
    # if request.user.role == "super_admin":
    #     messages.warning(
    #         request, "Суперадминистратор не может регистрировать автосервис"
    #     )
    #     return redirect("core:admin_panel")

    if request.method == "POST":
        form = AutoServiceRegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Создаем автосервис
                autoservice = form.save()

                # Привязываем пользователя к автосервису и сохраняем роль администратора
                # для будущей активации
                request.user.autoservice = autoservice
                request.user.previous_role = (
                    "autoservice_admin"  # Сохраняем роль для активации
                )
                request.user.save()

                # Отправляем уведомление суперадминистратору
                send_autoservice_registration_notification(autoservice, request.user)
                
                # Создаем уведомления для всех суперадминистраторов в системе
                superadmins = User.objects.filter(role="super_admin", is_active=True)
                for superadmin in superadmins:
                    add_notification(
                        user=superadmin,
                        title="Новый автосервис зарегистрирован",
                        message=f"Зарегистрирован новый автосервис '{autoservice.name}' в регионе '{autoservice.region.name}'. Требуется модерация.",
                        level="info"
                    )
                
                # Создаем уведомление для регистрирующегося пользователя
                add_notification(
                    user=request.user,
                    title="Автосервис зарегистрирован",
                    message=f"Ваш автосервис '{autoservice.name}' успешно зарегистрирован и ожидает активации модератором. Вы получите уведомление после активации.",
                    level="success"
                )

                messages.success(
                    request,
                    "Автосервис успешно зарегистрирован! "
                    "Вы будете назначены администратором после активации автосервиса модератором.",
                )

                # Перенаправляем на главную страницу
                return redirect("core:landing")

            except Exception as e:
                messages.error(request, f"Ошибка при регистрации автосервиса: {str(e)}")
                print(f"Ошибка регистрации автосервиса: {str(e)}")  # Для отладки
    else:
        form = AutoServiceRegistrationForm()

    return render(
        request,
        "core/autoservice_register.html",
        {"form": form, "title": "Регистрация автосервиса"},
    )


def send_autoservice_registration_notification(autoservice, user):
    """Отправляет уведомление суперадминистратору о регистрации нового автосервиса"""
    try:
        # Получаем email суперадминистратора
        superadmins = User.objects.filter(role="super_admin", is_active=True)
        print(f"e-mail to admin: {[admin.email for admin in superadmins]}")
        if not superadmins.exists():
            return

        subject = f"Новый автосервис: {autoservice.name}"
        message = f"""
Зарегистрирован новый автосервис:

Название: {autoservice.name}
Регион: {autoservice.region.name}
Адрес: {autoservice.address}
Телефон: {autoservice.phone}
Email: {autoservice.email}
Описание: {autoservice.description}

Будущий администратор:
Имя: {user.first_name} {user.last_name}
Email: {user.email}

Автосервис неактивен. При активации пользователь получит роль администратора автосервиса.
Для активации автосервиса перейдите в панель администратора.
        """

        # Отправляем email всем суперадминистраторам
        recipient_list = [admin.email for admin in superadmins]

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )

    except Exception as e:
        # Логируем ошибку, но не прерываем процесс регистрации
        print(f"Ошибка отправки email: {str(e)}")


@login_required
@login_required
@require_http_methods(["GET", "POST"])
def order_create(request, autoservice_id, service_id):
    """Создание заказа клиентом (только для авторизованных пользователей)"""
    autoservice = get_object_or_404(AutoService, id=autoservice_id)
    service = get_object_or_404(Service, id=service_id, autoservice=autoservice)

    if request.method == "POST":
        form = OrderCreateForm(request.POST, service=service, user=request.user, autoservice=autoservice)
        if form.is_valid():
            order = form.save()
            
            # Создаем уведомление для пользователя
            add_notification(
                user=request.user,
                title="Заказ успешно создан",
                message=f"Ваш заказ №{order.id} на услугу '{order.service.name}' в автосервисе '{order.autoservice.name}' успешно создан. Мы свяжемся с вами для подтверждения.",
                level="success"
            )
            
            # Создаем уведомления для сотрудников автосервиса
            autoservice_staff = order.autoservice.user_set.filter(
                role__in=['autoservice_admin', 'manager'],
                is_active=True
            )
            
            for staff_member in autoservice_staff:
                add_notification(
                    user=staff_member,
                    title="Новый заказ",
                    message=f"Получен новый заказ №{order.id} в автосервис '{order.autoservice.name}' на услугу '{order.service.name}' от клиента {order.get_client_name()}. Требуется обработка.",
                    level="info"
                )
            
            messages.success(
                request,
                f"Ваш заказ №{order.id} успешно создан! Мы свяжемся с вами в ближайшее время.",
            )
            
            return redirect("core:order_success", order_id=order.id)
    else:
        form = OrderCreateForm(service=service, user=request.user, autoservice=autoservice)

    context = {
        "form": form,
        "autoservice": autoservice,
        "service": service,
        "title": f"Заказать услугу: {service.name}",
    }

    return render(request, "core/order_create.html", context)


@require_http_methods(["GET"])
def order_success(request, order_id):
    """Страница успешного создания заказа"""
    order = get_object_or_404(Order, id=order_id)

    context = {
        "order": order,
        "title": "Заказ успешно создан",
    }

    return render(request, "core/order_success.html", context)


@require_http_methods(["GET"])
def check_masters_availability(request, autoservice_id):
    """API для проверки доступности мастеров на определенную дату и время"""
    try:
        autoservice = get_object_or_404(AutoService, id=autoservice_id)
        date_str = request.GET.get('date')
        time_str = request.GET.get('time')
        
        if not date_str or time_str is None:
            return JsonResponse({'error': 'Необходимо указать дату и время'}, status=400)
        
        from datetime import datetime, date, time
        try:
            check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            check_time = datetime.strptime(time_str, '%H:%M').time()
            check_datetime = datetime.combine(check_date, check_time)
        except ValueError:
            return JsonResponse({'error': 'Неверный формат даты или времени'}, status=400)
        
        # Получаем всех мастеров автосервиса
        masters = User.objects.filter(
            autoservice=autoservice,
            role='master',
            is_active=True
        ).order_by('last_name', 'first_name', 'username')
        
        masters_info = []
        for master in masters:
            is_working = is_master_working_at_datetime(master, check_datetime)
            schedule = get_master_schedule_for_date(master, check_date)
            
            # Проверяем занятость мастера другими заказами
            conflicting_orders = Order.objects.filter(
                assigned_master=master,
                preferred_date=check_date,
                status__in=['confirmed', 'in_progress']
            )
            
            is_busy = False
            busy_reason = ""
            
            for order in conflicting_orders:
                order_duration = order.estimated_duration or 60
                order_start = datetime.combine(order.preferred_date, order.preferred_time)
                order_end = order_start + timedelta(minutes=order_duration)
                
                # Проверяем пересечение времени (примерная длительность заказа 60 минут)
                check_end = check_datetime + timedelta(minutes=60)
                if (check_datetime < order_end and check_end > order_start):
                    is_busy = True
                    busy_reason = f"Занят заказом №{order.id} ({order.preferred_time.strftime('%H:%M')}-{order_end.strftime('%H:%M')})"
                    break
            
            master_info = {
                'id': master.id,
                'name': master.get_full_name() or master.username,
                'is_available': is_working and not is_busy,
                'is_working': is_working,
                'is_busy': is_busy,
                'busy_reason': busy_reason,
                'schedule_info': None,
                'unavailable_reason': None
            }
            
            if not is_working and schedule:
                if not schedule.is_working_day(check_date):
                    master_info['unavailable_reason'] = 'Не рабочий день'
                else:
                    master_info['unavailable_reason'] = f'Время работы: {schedule.start_time.strftime("%H:%M")}-{schedule.end_time.strftime("%H:%M")}'
            elif not schedule:
                master_info['unavailable_reason'] = 'Нет активного графика'
            elif is_working and schedule:
                master_info['schedule_info'] = f'{schedule.start_time.strftime("%H:%M")}-{schedule.end_time.strftime("%H:%M")}'
            
            masters_info.append(master_info)
        
        return JsonResponse({
            'masters': masters_info,
            'date': date_str,
            'time': time_str
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_available_time_slots(request, autoservice_id):
    """API для получения доступных временных слотов на определенную дату"""
    try:
        autoservice = get_object_or_404(AutoService, id=autoservice_id)
        date_str = request.GET.get('date')
        preferred_master_id = request.GET.get('master_id')  # Опционально
        
        if not date_str:
            return JsonResponse({'error': 'Необходимо указать дату'}, status=400)
        
        from datetime import datetime, date, time, timedelta
        try:
            check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Неверный формат даты'}, status=400)
        
        # Определяем мастеров для проверки
        if preferred_master_id:
            # Если выбран конкретный мастер
            masters = User.objects.filter(
                id=preferred_master_id,
                autoservice=autoservice,
                role='master',
                is_active=True
            )
        else:
            # Все мастера автосервиса
            masters = User.objects.filter(
                autoservice=autoservice,
                role='master',
                is_active=True
            )
        
        # Генерируем временные слоты с 8:00 до 20:00 с интервалом 30 минут
        available_slots = []
        current_time = time(8, 0)  # Начинаем с 8:00
        end_time = time(20, 0)     # Заканчиваем в 20:00
        
        while current_time < end_time:
            slot_datetime = datetime.combine(check_date, current_time)
            slot_available = False
            available_masters = []
            
            # Проверяем каждого мастера для этого слота
            for master in masters:
                # Проверяем график работы мастера
                if not is_master_working_at_datetime(master, slot_datetime):
                    continue
                
                # Проверяем занятость заказами
                is_busy = False
                conflicting_orders = Order.objects.filter(
                    assigned_master=master,
                    preferred_date=check_date,
                    status__in=['confirmed', 'in_progress']
                )
                
                for order in conflicting_orders:
                    order_duration = order.estimated_duration or 60
                    order_start = datetime.combine(order.preferred_date, order.preferred_time)
                    order_end = order_start + timedelta(minutes=order_duration)
                    
                    # Проверяем пересечение (предполагаем длительность нового заказа 60 минут)
                    slot_end = slot_datetime + timedelta(minutes=60)
                    if (slot_datetime < order_end and slot_end > order_start):
                        is_busy = True
                        break
                
                if not is_busy:
                    slot_available = True
                    available_masters.append({
                        'id': master.id,
                        'name': master.get_full_name() or master.username
                    })
            
            if slot_available:
                available_slots.append({
                    'time': current_time.strftime('%H:%M'),
                    'available_masters_count': len(available_masters),
                    'available_masters': available_masters[:3] if not preferred_master_id else available_masters  # Показываем до 3 мастеров
                })
            
            # Переходим к следующему слоту (прибавляем 30 минут)
            current_datetime = datetime.combine(date.today(), current_time)
            next_datetime = current_datetime + timedelta(minutes=30)
            current_time = next_datetime.time()
        
        return JsonResponse({
            'date': date_str,
            'available_slots': available_slots,
            'preferred_master_id': preferred_master_id,
            'total_masters': masters.count()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# УПРАВЛЕНИЕ АВТОМОБИЛЯМИ ПОЛЬЗОВАТЕЛЯ
# =============================================================================

@login_required
def user_cars_list(request):
    """Список автомобилей пользователя"""
    cars = Car.objects.filter(owner=request.user).order_by('-is_default', '-created_at')
    
    context = {
        'title': 'Мои автомобили',
        'cars': cars,
    }
    
    return render(request, 'core/user_cars_list.html', context)


@login_required
def user_car_add(request):
    """Добавление автомобиля пользователем"""
    if request.method == 'POST':
        form = CarForm(request.POST, user=request.user)
        if form.is_valid():
            car = form.save()
            
            # Создаем уведомление о добавлении автомобиля
            add_notification(
                user=request.user,
                title="Автомобиль добавлен",
                message=f"Автомобиль '{car}' успешно добавлен в ваш гараж. Теперь вы можете использовать его при оформлении заказов.",
                level="success"
            )
            
            messages.success(
                request, 
                f'Автомобиль "{car}" успешно добавлен!'
            )
            return redirect('core:user_cars_list')
    else:
        form = CarForm(user=request.user)
    
    context = {
        'title': 'Добавить автомобиль',
        'form': form,
    }
    
    return render(request, 'core/user_car_add.html', context)


@login_required
def user_car_edit(request, car_id):
    """Редактирование автомобиля пользователем"""
    car = get_object_or_404(Car, id=car_id, owner=request.user)
    
    if request.method == 'POST':
        form = CarForm(request.POST, instance=car, user=request.user)
        if form.is_valid():
            car = form.save()
            
            # Создаем уведомление об обновлении автомобиля
            add_notification(
                user=request.user,
                title="Автомобиль обновлен",
                message=f"Информация об автомобиле '{car}' успешно обновлена.",
                level="success"
            )
            
            messages.success(
                request, 
                f'Автомобиль "{car}" успешно обновлен!'
            )
            return redirect('core:user_cars_list')
    else:
        form = CarForm(instance=car, user=request.user)
    
    context = {
        'title': f'Редактировать автомобиль: {car}',
        'form': form,
        'car': car,
        'is_edit': True,
    }
    
    return render(request, 'core/user_car_add.html', context)


@login_required  
@require_POST
def user_car_delete(request, car_id):
    """Удаление автомобиля пользователем"""
    car = get_object_or_404(Car, id=car_id, owner=request.user)
    
    # Проверяем, есть ли активные заказы с этим автомобилем
    active_orders = Order.objects.filter(
        car=car, 
        status__in=['pending', 'confirmed', 'in_progress']
    ).count()
    
    if active_orders > 0:
        messages.error(
            request,
            f'Нельзя удалить автомобиль "{car}". У вас есть {active_orders} активных заказов с этим автомобилем.'
        )
    else:
        car_name = str(car)
        
        # Создаем уведомление об удалении автомобиля
        add_notification(
            user=request.user,
            title="Автомобиль удален",
            message=f"Автомобиль '{car_name}' удален из вашего гаража.",
            level="info"
        )
        
        car.delete()
        messages.success(request, f'Автомобиль "{car_name}" удален.')
    
    return redirect('core:user_cars_list')


@login_required
@require_POST  
def user_car_set_default(request, car_id):
    """Установка автомобиля как основного"""
    car = get_object_or_404(Car, id=car_id, owner=request.user)
    
    # Убираем флаг "основной" у всех других автомобилей пользователя
    Car.objects.filter(owner=request.user).update(is_default=False)
    
    # Устанавливаем выбранный автомобиль как основной
    car.is_default = True
    car.save()
    
    # Создаем уведомление об установке автомобиля как основного
    add_notification(
        user=request.user,
        title="Основной автомобиль изменен",
        message=f"Автомобиль '{car}' установлен как основной. Он будет автоматически выбираться при создании заказов.",
        level="info"
    )
    
    messages.success(request, f'Автомобиль "{car}" установлен как основной.')
    return redirect('core:user_cars_list')


# === Управление заказами пользователя ===

@login_required
def user_orders_list(request):
    """Список заказов пользователя с фильтрами"""
    # Получаем все заказы пользователя
    orders = Order.objects.filter(client=request.user).select_related(
        'autoservice', 'service', 'car'
    ).order_by('-created_at')
    
    # Фильтры
    status_filter = request.GET.get('status')
    autoservice_filter = request.GET.get('autoservice')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Применяем фильтры
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if autoservice_filter:
        orders = orders.filter(autoservice_id=autoservice_filter)
    
    if date_from:
        orders = orders.filter(preferred_date__gte=date_from)
        
    if date_to:
        orders = orders.filter(preferred_date__lte=date_to)
    
    # Получаем данные для фильтров
    user_autoservices = AutoService.objects.filter(
        orders__client=request.user
    ).distinct().order_by('name')
    
    # Статистика заказов
    orders_stats = {
        'total': orders.count(),
        'pending': orders.filter(status='pending').count(),
        'confirmed': orders.filter(status='confirmed').count(),
        'in_progress': orders.filter(status='in_progress').count(),
        'completed': orders.filter(status='completed').count(),
        'cancelled': orders.filter(status='cancelled').count(),
    }
    
    context = {
        'title': 'Мои заказы',
        'orders': orders,
        'orders_stats': orders_stats,
        'user_autoservices': user_autoservices,
        'status_choices': Order.STATUS_CHOICES,
        # Передаем текущие фильтры обратно в шаблон
        'current_filters': {
            'status': status_filter,
            'autoservice': int(autoservice_filter) if autoservice_filter else None,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'core/user_orders_list.html', context)


@login_required
def user_order_detail(request, order_id):
    """Детальная информация о заказе пользователя"""
    order = get_object_or_404(
        Order.objects.select_related('autoservice', 'service', 'car'),
        id=order_id,
        client=request.user
    )
    
    context = {
        'title': f'Заказ №{order.id}',
        'order': order,
        'can_cancel': order.status in ['pending', 'confirmed'],
    }
    
    return render(request, 'core/user_order_detail.html', context)


@login_required
@require_POST
def user_order_cancel(request, order_id):
    """Отмена заказа пользователем"""
    order = get_object_or_404(Order, id=order_id, client=request.user)
    
    # Проверяем, можно ли отменить заказ
    if order.status not in ['pending', 'confirmed']:
        messages.error(
            request,
            f'Заказ №{order.id} нельзя отменить. Текущий статус: {order.get_status_display()}'
        )
    else:
        order.status = 'cancelled'
        order.save()
        
        # Создаем уведомление для пользователя
        add_notification(
            user=request.user,
            title="Заказ отменен",
            message=f"Ваш заказ №{order.id} на услугу '{order.service.name}' в автосервисе '{order.autoservice.name}' успешно отменен.",
            level="info"
        )
        
        # Создаем уведомления для сотрудников автосервиса об отмене
        autoservice_staff = order.autoservice.user_set.filter(
            role__in=['autoservice_admin', 'manager'],
            is_active=True
        )
        
        for staff_member in autoservice_staff:
            add_notification(
                user=staff_member,
                title="Заказ отменен клиентом",
                message=f"Клиент {order.get_client_name()} отменил заказ №{order.id} на услугу '{order.service.name}'.",
                level="warning"
            )
        
        messages.success(
            request,
            f'Заказ №{order.id} успешно отменен.'
        )
        
        # Отправляем уведомление автосервису
        try:
            send_mail(
                subject=f'Отмена заказа №{order.id}',
                message=f'Клиент {order.get_client_name()} отменил заказ №{order.id} на услугу "{order.service.name}".',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.autoservice.email] if order.autoservice.email else [],
                fail_silently=True,
            )
        except Exception:
            pass  # Не прерываем работу, если email не отправился
    
    return redirect('core:user_order_detail', order_id=order.id)


# ============== VIEWS ДЛЯ УВЕДОМЛЕНИЙ ==============

@login_required
def notifications_list(request):
    """Список уведомлений пользователя"""
    notifications = Notification.get_user_notifications(
        user=request.user,
        include_read=True
    )
    
    # Отмечаем все непрочитанные как прочитанные при просмотре списка
    unread_notifications = notifications.filter(is_read=False)
    for notification in unread_notifications:
        notification.mark_as_read()
    
    context = {
        'notifications': notifications,
        'title': 'Уведомления'
    }
    
    return render(request, 'core/notifications_list.html', context)


@login_required
@require_http_methods(["POST"])
def notification_mark_read(request, notification_id):
    """Отметить уведомление как прочитанное"""
    notification = get_object_or_404(
        Notification,
        id=notification_id,
        user=request.user,
        is_deleted=False
    )
    
    notification.mark_as_read()
    
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def notification_delete(request, notification_id):
    """Удалить уведомление (мягкое удаление)"""
    try:
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            user=request.user
        )
        
        notification.mark_as_deleted()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
def notification_get_count(request):
    """Получить количество непрочитанных уведомлений (AJAX)"""
    count = Notification.get_unread_count(request.user)
    return JsonResponse({'count': count})


@login_required
def notification_get_recent(request):
    """Получить последние уведомления для dropdown (AJAX)"""
    notifications = Notification.get_user_notifications(
        user=request.user,
        include_read=True,
        limit=5
    )
    
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'level': notification.level,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%d.%m.%Y %H:%M'),
        })
    
    return JsonResponse({
        'notifications': notifications_data,
        'count': len(notifications_data)
    })


# ============== УПРАВЛЕНИЕ ЗАКАЗАМИ АВТОСЕРВИСА ==============

@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_orders_list(request):
    """Список заказов автосервиса с фильтрами"""
    autoservice = request.user.autoservice
    
    # Получаем все заказы автосервиса
    orders = Order.objects.filter(autoservice=autoservice).select_related(
        'client', 'service', 'car', 'assigned_master'
    ).order_by('-created_at')
    
    # Фильтры
    status_filter = request.GET.get('status')
    master_filter = request.GET.get('master')
    service_filter = request.GET.get('service')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Применяем фильтры
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if master_filter:
        if master_filter == 'unassigned':
            orders = orders.filter(assigned_master__isnull=True)
        else:
            orders = orders.filter(assigned_master_id=master_filter)
    
    if service_filter:
        orders = orders.filter(service_id=service_filter)
    
    if date_from:
        orders = orders.filter(preferred_date__gte=date_from)
        
    if date_to:
        orders = orders.filter(preferred_date__lte=date_to)
    
    # Получаем данные для фильтров
    masters = User.objects.filter(
        autoservice=autoservice,
        role='master',
        is_active=True
    ).order_by('last_name', 'first_name', 'username')
    
    services = Service.objects.filter(
        autoservice=autoservice,
        is_active=True
    ).order_by('name')
    
    # Статистика заказов
    orders_stats = {
        'total': orders.count(),
        'pending': orders.filter(status='pending').count(),
        'confirmed': orders.filter(status='confirmed').count(),
        'in_progress': orders.filter(status='in_progress').count(),
        'completed': orders.filter(status='completed').count(),
        'cancelled': orders.filter(status='cancelled').count(),
        'unassigned': orders.filter(assigned_master__isnull=True).count(),
    }
    
    context = {
        'title': f'Заказы - {autoservice.name}',
        'autoservice': autoservice,
        'orders': orders,
        'orders_stats': orders_stats,
        'masters': masters,
        'services': services,
        'status_choices': Order.STATUS_CHOICES,
        # Передаем текущие фильтры обратно в шаблон
        'current_filters': {
            'status': status_filter,
            'master': master_filter,
            'service': int(service_filter) if service_filter else None,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'core/autoservice_admin/orders_list.html', context)


@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_order_detail(request, order_id):
    """Детальная информация о заказе автосервиса"""
    autoservice = request.user.autoservice
    order = get_object_or_404(
        Order.objects.select_related('client', 'service', 'car', 'assigned_master'),
        id=order_id,
        autoservice=autoservice
    )
    
    # Получаем доступных мастеров с информацией о графиках
    available_masters = User.objects.filter(
        autoservice=autoservice,
        role='master',
        is_active=True
    ).order_by('last_name', 'first_name', 'username')
    
    # Добавляем информацию о графиках мастеров для даты заказа
    masters_with_schedule = []
    if order.preferred_date:
        from datetime import datetime
        order_datetime = datetime.combine(order.preferred_date, order.preferred_time)
        
        for master in available_masters:
            is_working = is_master_working_at_datetime(master, order_datetime)
            schedule = get_master_schedule_for_date(master, order.preferred_date)
            
            master_info = {
                'master': master,
                'is_working': is_working,
                'schedule': schedule,
            }
            
            if not is_working and schedule:
                if not schedule.is_working_day(order.preferred_date):
                    master_info['unavailable_reason'] = 'Не рабочий день'
                else:
                    master_info['unavailable_reason'] = f'Время работы: {schedule.start_time.strftime("%H:%M")}-{schedule.end_time.strftime("%H:%M")}'
            elif not schedule:
                master_info['unavailable_reason'] = 'Нет активного графика'
            
            masters_with_schedule.append(master_info)
    else:
        # Если дата не указана, просто добавляем мастеров без проверки графика
        for master in available_masters:
            masters_with_schedule.append({
                'master': master,
                'is_working': True,  # Предполагаем доступность
                'schedule': None,
            })
    
    context = {
        'title': f'Заказ №{order.id} - {autoservice.name}',
        'autoservice': autoservice,
        'order': order,
        'available_masters': available_masters,
        'masters_with_schedule': masters_with_schedule,
        'can_confirm': order.status == 'pending',
        'can_cancel': order.status in ['pending', 'confirmed'],
        'can_start': order.status == 'confirmed' and order.assigned_master,
        'can_complete': order.status == 'in_progress',
    }
    
    return render(request, 'core/autoservice_admin/order_detail.html', context)


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def autoservice_order_assign_master(request, order_id):
    """Назначение мастера на заказ с проверкой графика работы"""
    autoservice = request.user.autoservice
    order = get_object_or_404(Order, id=order_id, autoservice=autoservice)
    
    master_id = request.POST.get('master_id')
    
    if not master_id:
        messages.error(request, "Выберите мастера")
        return redirect('core:autoservice_order_detail', order_id=order.id)
    
    try:
        master = get_object_or_404(
            User,
            id=master_id,
            autoservice=autoservice,
            role='master',
            is_active=True
        )
        
        # Проверяем график работы мастера на дату заказа
        from datetime import datetime
        order_datetime = datetime.combine(order.preferred_date, order.preferred_time)
        
        if not is_master_working_at_datetime(master, order_datetime):
            schedule = get_master_schedule_for_date(master, order.preferred_date)
            if not schedule:
                messages.error(
                    request,
                    f"У мастера {master.get_full_name() or master.username} нет активного графика работы на {order.preferred_date.strftime('%d.%m.%Y')}"
                )
            elif not schedule.is_working_day(order.preferred_date):
                messages.error(
                    request,
                    f"Мастер {master.get_full_name() or master.username} не работает {order.preferred_date.strftime('%d.%m.%Y')} согласно графику"
                )
            else:
                messages.error(
                    request,
                    f"Мастер {master.get_full_name() or master.username} не работает в {order.preferred_time.strftime('%H:%M')} согласно графику ({schedule.start_time.strftime('%H:%M')}-{schedule.end_time.strftime('%H:%M')})"
                )
            return redirect('core:autoservice_order_detail', order_id=order.id)
        
        # Проверяем, не занят ли мастер в это время другими заказами
        conflicting_orders = Order.objects.filter(
            assigned_master=master,
            preferred_date=order.preferred_date,
            status__in=['confirmed', 'in_progress']
        ).exclude(id=order.id)
        
        # Проверяем пересечение по времени
        order_duration = order.estimated_duration or 60  # По умолчанию 60 минут
        order_start = datetime.combine(order.preferred_date, order.preferred_time)
        order_end = order_start + timedelta(minutes=order_duration)
        
        for conflicting_order in conflicting_orders:
            conflict_duration = conflicting_order.estimated_duration or 60
            conflict_start = datetime.combine(conflicting_order.preferred_date, conflicting_order.preferred_time)
            conflict_end = conflict_start + timedelta(minutes=conflict_duration)
            
            # Проверяем пересечение времени
            if (order_start < conflict_end and order_end > conflict_start):
                messages.error(
                    request,
                    f"Мастер {master.get_full_name() or master.username} уже занят в это время заказом №{conflicting_order.id} ({conflicting_order.preferred_time.strftime('%H:%M')}-{conflict_end.strftime('%H:%M')})"
                )
                return redirect('core:autoservice_order_detail', order_id=order.id)
        
        # Назначаем мастера
        order.assigned_master = master
        order.save()
        
        # Создаем уведомления
        add_notification(
            user=master,
            title="Новое назначение",
            message=f"Вам назначен заказ №{order.id} на услугу '{order.service.name}' в автосервисе '{autoservice.name}' на {order.preferred_date.strftime('%d.%m.%Y')} в {order.preferred_time.strftime('%H:%M')}.",
            level="info"
        )
        
        # Уведомляем администратора автосервиса о назначении
        try:
            autoservice_admin = User.objects.filter(
                autoservice=autoservice,
                role='autoservice_admin',
                is_active=True
            ).first()
            
            if autoservice_admin and autoservice_admin != request.user:  # Если назначение делает не сам администратор
                add_notification(
                    user=autoservice_admin,
                    title="Назначен мастер",
                    message=f"Заказ №{order.id} назначен мастеру {master.get_full_name() or master.username}. Клиент: {order.get_client_name()}.",
                    level="info"
                )
        except Exception:
            pass  # Игнорируем ошибки уведомлений, чтобы не прерывать основной процесс
        
        messages.success(
            request,
            f"Заказ №{order.id} назначен мастеру {master.get_full_name() or master.username}"
        )
        
    except Exception as e:
        messages.error(request, f"Ошибка при назначении мастера: {str(e)}")
    
    return redirect('core:autoservice_order_detail', order_id=order.id)


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def autoservice_order_confirm(request, order_id):
    """Подтверждение заказа"""
    autoservice = request.user.autoservice
    order = get_object_or_404(Order, id=order_id, autoservice=autoservice)
    
    if order.status != 'pending':
        messages.error(request, f"Заказ №{order.id} нельзя подтвердить. Текущий статус: {order.get_status_display()}")
        return redirect('core:autoservice_order_detail', order_id=order.id)
    
    order.status = 'confirmed'
    order.save()
    
    # Формируем сообщение для клиента
    client_message = f"Ваш заказ №{order.id} на услугу '{order.service.name}' подтвержден автосервисом '{autoservice.name}'. Дата: {order.preferred_date.strftime('%d.%m.%Y')}."
    
    if order.assigned_master:
        client_message += f" Назначенный мастер: {order.assigned_master.get_full_name() or order.assigned_master.username}."
    else:
        client_message += " Мастер будет назначен позднее."
    
    # Создаем уведомления
    add_notification(
        user=order.client,
        title="Заказ подтвержден",
        message=client_message,
        level="success"
    )
    
    if order.assigned_master:
        add_notification(
            user=order.assigned_master,
            title="Заказ подтвержден",
            message=f"Заказ №{order.id} на услугу '{order.service.name}' в автосервисе '{autoservice.name}', назначенный на вас, подтвержден.",
            level="success"
        )
    
    messages.success(request, f"Заказ №{order.id} подтвержден")
    
    return redirect('core:autoservice_order_detail', order_id=order.id)


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def autoservice_order_cancel(request, order_id):
    """Отмена заказа автосервисом"""
    autoservice = request.user.autoservice
    order = get_object_or_404(Order, id=order_id, autoservice=autoservice)
    
    if order.status not in ['pending', 'confirmed']:
        messages.error(request, f"Заказ №{order.id} нельзя отменить. Текущий статус: {order.get_status_display()}")
        return redirect('core:autoservice_order_detail', order_id=order.id)
    
    cancel_reason = request.POST.get('cancel_reason', '')
    
    order.status = 'cancelled'
    order.save()
    
    # Создаем уведомления
    cancel_message = f"Ваш заказ №{order.id} на услугу '{order.service.name}' отменен автосервисом '{autoservice.name}'."
    if cancel_reason:
        cancel_message += f" Причина: {cancel_reason}"
    
    add_notification(
        user=order.client,
        title="Заказ отменен",
        message=cancel_message,
        level="warning"
    )
    
    if order.assigned_master:
        add_notification(
            user=order.assigned_master,
            title="Заказ отменен",
            message=f"Заказ №{order.id} на услугу '{order.service.name}', назначенный на вас, отменен автосервисом.",
            level="warning"
        )
    
    messages.success(request, f"Заказ №{order.id} отменен")
    
    return redirect('core:autoservice_order_detail', order_id=order.id)


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def autoservice_order_start(request, order_id):
    """Начать выполнение заказа"""
    autoservice = request.user.autoservice
    order = get_object_or_404(Order, id=order_id, autoservice=autoservice)
    
    if order.status != 'confirmed' or not order.assigned_master:
        messages.error(request, f"Заказ №{order.id} нельзя начать. Проверьте статус и назначение мастера.")
        return redirect('core:autoservice_order_detail', order_id=order.id)
    
    order.status = 'in_progress'
    order.save()
    
    # Создаем уведомления
    add_notification(
        user=order.client,
        title="Работа начата",
        message=f"Мастер {order.assigned_master.get_full_name() or order.assigned_master.username} начал выполнение заказа №{order.id}.",
        level="info"
    )
    
    add_notification(
        user=order.assigned_master,
        title="Работа начата",
        message=f"Заказ №{order.id} на услугу '{order.service.name}' переведен в статус 'В работе'.",
        level="info"
    )
    
    messages.success(request, f"Заказ №{order.id} переведен в работу")
    
    return redirect('core:autoservice_order_detail', order_id=order.id)


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def autoservice_order_complete(request, order_id):
    """Завершить заказ"""
    autoservice = request.user.autoservice
    order = get_object_or_404(Order, id=order_id, autoservice=autoservice)
    
    if order.status != 'in_progress':
        messages.error(request, f"Заказ №{order.id} нельзя завершить. Текущий статус: {order.get_status_display()}")
        return redirect('core:autoservice_order_detail', order_id=order.id)
    
    completion_notes = request.POST.get('completion_notes', '')
    
    order.status = 'completed'
    from django.utils import timezone
    order.completed_at = timezone.now()
    order.save()
    
    # Создаем уведомления
    completion_message = f"Ваш заказ №{order.id} на услугу '{order.service.name}' успешно выполнен!"
    if completion_notes:
        completion_message += f" Комментарий мастера: {completion_notes}"
    
    add_notification(
        user=order.client,
        title="Заказ выполнен",
        message=completion_message,
        level="success"
    )
    
    # Отправляем уведомление с предложением оставить отзыв
    from django.urls import reverse
    review_url = request.build_absolute_uri(reverse('core:order_review_create', args=[order.id]))
    add_notification(
        user=order.client,
        title="Оставьте отзыв о выполненной работе",
        message=f'Ваш заказ №{order.id} успешно выполнен! Поделитесь своим мнением о качестве работы. Ваш отзыв поможет другим клиентам сделать правильный выбор. <br><br><a href="{review_url}" class="btn btn-primary btn-sm"><i class="fas fa-star"></i> Оставить отзыв</a>',
        level="info"
    )
    
    if order.assigned_master:
        add_notification(
            user=order.assigned_master,
            title="Заказ завершен",
            message=f"Заказ №{order.id} на услугу '{order.service.name}' успешно завершен.",
            level="success"
        )
    
    messages.success(request, f"Заказ №{order.id} завершен")
    
    return redirect('core:autoservice_order_detail', order_id=order.id)


@login_required
@user_passes_test(is_autoservice_admin)
@login_required
@user_passes_test(is_autoservice_admin)
def autoservice_workload_view(request):
    """Панель загрузки мастеров автосервиса с учетом графиков работы"""
    from datetime import datetime, timedelta, time
    from django.utils import timezone
    
    autoservice = request.user.autoservice
    
    # Получаем дату из параметров запроса или используем сегодня
    selected_date_str = request.GET.get('date')
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()
    
    # Получаем режим отображения (день/неделя)
    view_mode = request.GET.get('mode', 'day')  # day или week
    
    if view_mode == 'week':
        # Начало недели (понедельник)
        start_date = selected_date - timedelta(days=selected_date.weekday())
        end_date = start_date + timedelta(days=6)
        dates_range = [start_date + timedelta(days=i) for i in range(7)]
    else:
        # Один день
        start_date = end_date = selected_date
        dates_range = [selected_date]
    
    # Получаем всех мастеров автосервиса
    masters = User.objects.filter(
        autoservice=autoservice,
        role='master',
        is_active=True
    ).order_by('first_name', 'last_name', 'username')
    
    # Получаем заказы в выбранном диапазоне дат
    orders = Order.objects.filter(
        autoservice=autoservice,
        preferred_date__range=[start_date, end_date],
        status__in=['confirmed', 'in_progress']
    ).select_related('assigned_master', 'service', 'client').order_by('preferred_date', 'preferred_time')
    
    # Группируем заказы по мастерам и датам
    workload_data = {}
    for master in masters:
        workload_data[master.id] = {
            'master': master,
            'dates': {}
        }
        
        for date in dates_range:
            # Получаем график работы мастера на эту дату
            schedule = get_master_schedule_for_date(master, date)
            
            if schedule and schedule.is_working_day(date):
                # Мастер работает в этот день
                work_start = schedule.start_time
                work_end = schedule.end_time
                
                # Генерируем временные интервалы для рабочего дня мастера
                time_slots = []
                current_time = datetime.combine(date, work_start)
                end_time = datetime.combine(date, work_end)
                
                while current_time < end_time:
                    time_slots.append(current_time.time())
                    current_time += timedelta(minutes=30)
                
                workload_data[master.id]['dates'][date] = {
                    'is_working': True,
                    'work_start': work_start,
                    'work_end': work_end,
                    'schedule': schedule,
                    'orders': [],
                    'time_slots': {}
                }
                
                # Инициализируем все временные слоты как свободные
                for slot in time_slots:
                    workload_data[master.id]['dates'][date]['time_slots'][slot] = {
                        'status': 'free',
                        'order': None
                    }
            else:
                # Мастер не работает в этот день или график не задан
                workload_data[master.id]['dates'][date] = {
                    'is_working': False,
                    'work_start': None,
                    'work_end': None,
                    'schedule': schedule,
                    'orders': [],
                    'time_slots': {}
                }
    
    # Заполняем данные о занятости
    for order in orders:
        if order.assigned_master and order.assigned_master.id in workload_data:
            date = order.preferred_date
            master_id = order.assigned_master.id
            
            if date in workload_data[master_id]['dates'] and workload_data[master_id]['dates'][date]['is_working']:
                workload_data[master_id]['dates'][date]['orders'].append(order)
                
                # Отмечаем занятые временные слоты
                order_start_time = order.preferred_time
                order_duration = order.estimated_duration or 60  # По умолчанию 60 минут
                
                order_start = datetime.combine(date, order_start_time)
                order_end = order_start + timedelta(minutes=order_duration)
                
                time_slots = workload_data[master_id]['dates'][date]['time_slots']
                
                for slot in time_slots.keys():
                    slot_datetime = datetime.combine(date, slot)
                    slot_end = slot_datetime + timedelta(minutes=30)
                    
                    # Проверяем пересечение времени заказа со слотом
                    if (slot_datetime < order_end and slot_end > order_start):
                        workload_data[master_id]['dates'][date]['time_slots'][slot] = {
                            'status': 'busy',
                            'order': order
                        }
    
    # Заказы без назначенного мастера
    unassigned_orders = orders.filter(assigned_master__isnull=True)
    
    # Общие временные слоты для отображения (максимальный диапазон)
    default_work_start = time(8, 0)
    default_work_end = time(20, 0)
    
    all_time_slots = []
    current_time = datetime.combine(selected_date, default_work_start)
    end_time = datetime.combine(selected_date, default_work_end)
    
    while current_time < end_time:
        all_time_slots.append(current_time.time())
        current_time += timedelta(minutes=30)
    
    context = {
        'title': f'Панель загрузки - {autoservice.name}',
        'autoservice': autoservice,
        'selected_date': selected_date,
        'view_mode': view_mode,
        'dates_range': dates_range,
        'start_date': start_date,
        'end_date': end_date,
        'masters': masters,
        'workload_data': workload_data,
        'all_time_slots': all_time_slots,
        'unassigned_orders': unassigned_orders,
        'default_work_start': default_work_start,
        'default_work_end': default_work_end,
    }
    
    return render(request, 'core/autoservice_admin/workload.html', context)


@login_required
@login_required
@user_passes_test(is_autoservice_admin)
def work_schedule_list(request):
    """Список графиков работы мастеров"""
    autoservice = request.user.autoservice
    
    # Получаем всех мастеров автосервиса
    masters = User.objects.filter(
        autoservice=autoservice,
        role='master',
        is_active=True
    ).order_by('first_name', 'last_name', 'username')
    
    # Получаем графики работы с фильтрацией
    schedules_qs = WorkSchedule.objects.filter(
        master__autoservice=autoservice
    ).select_related('master').order_by('master__first_name', 'master__last_name', 'start_date')
    
    # Применяем фильтры
    master_filter = request.GET.get('master')
    schedule_type_filter = request.GET.get('schedule_type')
    is_active_filter = request.GET.get('is_active')
    
    if master_filter:
        schedules_qs = schedules_qs.filter(master_id=master_filter)
    
    if schedule_type_filter:
        schedules_qs = schedules_qs.filter(schedule_type=schedule_type_filter)
    
    if is_active_filter in ['true', 'false']:
        schedules_qs = schedules_qs.filter(is_active=is_active_filter == 'true')
    
    schedules = schedules_qs
    
    # Статистика
    masters_count = masters.count()
    active_schedules_count = WorkSchedule.objects.filter(
        master__autoservice=autoservice,
        is_active=True
    ).count()
    weekly_schedules_count = WorkSchedule.objects.filter(
        master__autoservice=autoservice,
        schedule_type='weekly'
    ).count()
    custom_schedules_count = WorkSchedule.objects.filter(
        master__autoservice=autoservice,
        schedule_type='custom'
    ).count()
    
    context = {
        'title': f'Графики работы - {autoservice.name}',
        'autoservice': autoservice,
        'masters': masters,
        'schedules': schedules,
        'masters_count': masters_count,
        'active_schedules_count': active_schedules_count,
        'weekly_schedules_count': weekly_schedules_count,
        'custom_schedules_count': custom_schedules_count,
    }
    
    return render(request, 'core/autoservice_admin/work_schedule_list.html', context)


@login_required
@user_passes_test(is_autoservice_admin)
def work_schedule_create(request):
    """Создание графика работы"""
    from .forms import WorkScheduleForm
    autoservice = request.user.autoservice
    
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, autoservice=autoservice)
        if form.is_valid():
            schedule = form.save()
            messages.success(request, f'График работы для {schedule.master.get_full_name() or schedule.master.username} создан')
            return redirect('core:work_schedule_list')
    else:
        form = WorkScheduleForm(autoservice=autoservice)
    
    context = {
        'title': f'Создание графика работы - {autoservice.name}',
        'form': form,
        'autoservice': autoservice,
    }
    
    return render(request, 'core/autoservice_admin/work_schedule_form.html', context)


@login_required
@user_passes_test(is_autoservice_admin)
def work_schedule_edit(request, schedule_id):
    """Редактирование графика работы"""
    from .forms import WorkScheduleForm
    autoservice = request.user.autoservice
    
    schedule = get_object_or_404(
        WorkSchedule,
        id=schedule_id,
        master__autoservice=autoservice
    )
    
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, instance=schedule, autoservice=autoservice)
        if form.is_valid():
            schedule = form.save()
            messages.success(request, f'График работы для {schedule.master.get_full_name() or schedule.master.username} обновлен')
            return redirect('core:work_schedule_list')
    else:
        form = WorkScheduleForm(instance=schedule, autoservice=autoservice)
    
    context = {
        'title': f'Редактирование графика работы - {autoservice.name}',
        'form': form,
        'schedule': schedule,
        'autoservice': autoservice,
    }
    
    return render(request, 'core/autoservice_admin/work_schedule_form.html', context)


@login_required
@user_passes_test(is_autoservice_admin)
@require_POST
def work_schedule_delete(request, schedule_id):
    """Удаление графика работы"""
    autoservice = request.user.autoservice
    
    schedule = get_object_or_404(
        WorkSchedule,
        id=schedule_id,
        master__autoservice=autoservice
    )
    
    master_name = schedule.master.get_full_name() or schedule.master.username
    schedule.delete()
    
    messages.success(request, f'График работы для {master_name} удален')
    return redirect('core:work_schedule_list')


# ============== СИСТЕМА ОТЗЫВОВ ==============

from .models import Review, ReviewReply
from .forms import (
    AutoServiceReviewForm,
    MasterReviewForm,
    ServiceReviewForm,
    ReviewReplyForm
)

def autoservice_reviews_list(request, autoservice_id):
    """Список отзывов об автосервисе"""
    autoservice = get_object_or_404(AutoService, id=autoservice_id, is_active=True)
    
    reviews = Review.objects.filter(
        autoservice=autoservice,
        is_approved=True
    ).select_related('author', 'reply').order_by('-created_at')
    
    # Вычисляем статистику
    total_reviews = reviews.count()
    if total_reviews > 0:
        avg_rating = sum(review.rating for review in reviews) / total_reviews
        rating_distribution = {}
        for i in range(1, 6):
            count = reviews.filter(rating=i).count()
            percentage = round((count * 100) / total_reviews, 1) if total_reviews > 0 else 0
            rating_distribution[i] = {
                'count': count,
                'percentage': percentage
            }
    else:
        avg_rating = 0
        rating_distribution = {i: {'count': 0, 'percentage': 0} for i in range(1, 6)}

    context = {
        'autoservice': autoservice,
        'reviews': reviews,
        'rating_stats': {
            'total': total_reviews,
            'average': round(avg_rating, 1),
            'breakdown': rating_distribution
        },
        'can_leave_review': request.user.is_authenticated,
    }
    
    return render(request, 'core/reviews/autoservice_reviews_list.html', context)


@login_required
def autoservice_review_create(request, autoservice_id):
    """Создание отзыва об автосервисе"""
    autoservice = get_object_or_404(AutoService, id=autoservice_id, is_active=True)
    
    # Проверяем, не оставлял ли пользователь уже отзыв
    existing_review = Review.objects.filter(
        author=request.user,
        autoservice=autoservice
    ).first()
    
    if existing_review:
        messages.warning(request, 'Вы уже оставили отзыв об этом автосервисе')
        return redirect('core:autoservice_reviews_list', autoservice_id=autoservice.id)
    
    if request.method == 'POST':
        form = AutoServiceReviewForm(request.POST, autoservice=autoservice)
        if form.is_valid():
            # Просто сохраняем форму и устанавливаем автора
            review = form.save(commit=False)
            review.author = request.user
            # Форма уже установила все нужные поля, теперь можно сохранять
            review.save()
            
            # Отправляем уведомление суперадминистратору о новом отзыве
            try:
                superadmins = User.objects.filter(role='super_admin', is_active=True)
                for superadmin in superadmins:
                    add_notification(
                        user=superadmin,
                        title="Новый отзыв на модерацию",
                        message=f"Пользователь {review.author.get_full_name() or review.author.username} оставил отзыв об автосервисе '{autoservice.name}'. Оценка: {review.rating}/5. Требуется модерация.",
                        level="info"
                    )
            except Exception:
                pass  # Игнорируем ошибки уведомлений
            
            messages.success(request, 'Спасибо за отзыв! Он будет опубликован после модерации.')
            return redirect('core:autoservice_reviews_list', autoservice_id=autoservice.id)
    else:
        form = AutoServiceReviewForm(autoservice=autoservice)
    
    context = {
        'form': form,
        'autoservice': autoservice,
        'title': f'Отзыв об автосервисе {autoservice.name}'
    }
    
    return render(request, 'core/reviews/review_create.html', context)


def master_reviews_list(request, master_id):
    """Список отзывов о мастере"""
    master = get_object_or_404(User, id=master_id, role='master', is_active=True)
    
    reviews = Review.objects.filter(
        reviewed_user=master,
        is_approved=True
    ).select_related('author', 'reply').order_by('-created_at')
      # Вычисляем статистику
    total_reviews = reviews.count()
    if total_reviews > 0:
        avg_rating = sum(review.rating for review in reviews) / total_reviews
        rating_distribution = {}
        for i in range(1, 6):
            count = reviews.filter(rating=i).count()
            percentage = round((count * 100) / total_reviews, 1) if total_reviews > 0 else 0
            rating_distribution[i] = {
                'count': count,
                'percentage': percentage
            }
    else:
        avg_rating = 0
        rating_distribution = {i: {'count': 0, 'percentage': 0} for i in range(1, 6)}

    context = {
        'master': master,
        'reviews': reviews,
        'rating_stats': {
            'total': total_reviews,
            'average': round(avg_rating, 1),
            'breakdown': rating_distribution
        },
        'can_leave_review': request.user.is_authenticated and request.user != master,
    }
    
    return render(request, 'core/reviews/master_reviews_list.html', context)


@login_required
def master_review_create(request, master_id):
    """Создание отзыва о мастере"""
    master = get_object_or_404(User, id=master_id, role='master', is_active=True)
    
    # Нельзя оставлять отзыв о самом себе
    if request.user == master:
        messages.error(request, 'Нельзя оставлять отзыв о самом себе')
        return redirect('core:master_reviews_list', master_id=master.id)
    
    # Проверяем, не оставлял ли пользователь уже отзыв
    existing_review = Review.objects.filter(
        author=request.user,
        reviewed_user=master
    ).first()
    
    if existing_review:
        messages.warning(request, 'Вы уже оставили отзыв об этом мастере')
        return redirect('core:master_reviews_list', master_id=master.id)
    
    if request.method == 'POST':
        form = MasterReviewForm(request.POST, master=master)
        if form.is_valid():
            review = form.save(commit=False)
            review.author = request.user
            review.save()
            
            # Отправляем уведомление суперадминистратору о новом отзыве
            try:
                superadmins = User.objects.filter(role='super_admin', is_active=True)
                for superadmin in superadmins:
                    add_notification(
                        user=superadmin,
                        title="Новый отзыв на модерацию",
                        message=f"Пользователь {review.author.get_full_name() or review.author.username} оставил отзыв о мастере '{master.get_full_name() or master.username}'. Оценка: {review.rating}/5. Требуется модерация.",
                        level="info"
                    )
            except Exception:
                pass  # Игнорируем ошибки уведомлений
            
            messages.success(request, 'Спасибо за отзыв! Он будет опубликован после модерации.')
            return redirect('core:master_reviews_list', master_id=master.id)
    else:
        form = MasterReviewForm(master=master)
    
    context = {
        'form': form,
        'master': master,
        'title': f'Отзыв о мастере {master.get_full_name()}'
    }
    
    return render(request, 'core/reviews/review_create.html', context)


def service_reviews_list(request, service_id):
    """Список отзывов об услуге"""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    
    reviews = Review.objects.filter(
        service=service,
        is_approved=True
    ).select_related('author', 'reply').order_by('-created_at')
      # Вычисляем статистику
    total_reviews = reviews.count()
    if total_reviews > 0:
        avg_rating = sum(review.rating for review in reviews) / total_reviews
        rating_distribution = {}
        for i in range(1, 6):
            count = reviews.filter(rating=i).count()
            percentage = round((count * 100) / total_reviews, 1) if total_reviews > 0 else 0
            rating_distribution[i] = {
                'count': count,
                'percentage': percentage
            }
    else:
        avg_rating = 0
        rating_distribution = {i: {'count': 0, 'percentage': 0} for i in range(1, 6)}

    context = {
        'service': service,
        'reviews': reviews,
        'rating_stats': {
            'total': total_reviews,
            'average': round(avg_rating, 1),
            'breakdown': rating_distribution
        },
        'can_leave_review': request.user.is_authenticated,
    }
    
    return render(request, 'core/reviews/service_reviews_list.html', context)


@login_required
def service_review_create(request, service_id):
    """Создание отзыва об услуге"""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    
    # Проверяем, если есть параметр order_id - это отзыв по заказу
    order_id = request.GET.get('order_id')
    order = None
    if order_id:
        order = get_object_or_404(Order, id=order_id, client=request.user, service=service, status='completed')
        
        # Проверяем, не оставлен ли уже отзыв по этому заказу
        if order.review_left:
            messages.warning(request, 'Вы уже оставили отзыв по этому заказу')
            return redirect('core:user_order_detail', order_id=order.id)
    else:
        # Обычная проверка на существующий отзыв об услуге
        existing_review = Review.objects.filter(
            author=request.user,
            service=service
        ).first()
        
        if existing_review:
            messages.warning(request, 'Вы уже оставили отзыв об этой услуге')
            return redirect('core:service_reviews_list', service_id=service.id)

    if request.method == 'POST':
        form = ServiceReviewForm(request.POST, service=service)
        if form.is_valid():
            review = form.save(commit=False)
            review.author = request.user
            
            # Если это отзыв по заказу, связываем его с заказом
            if order:
                review.order = order
                order.review_left = True
                order.save()
            
            review.save()
            
            # Отправляем уведомление суперадминистратору о новом отзыве
            try:
                superadmins = User.objects.filter(role='super_admin', is_active=True)
                message_text = f"Пользователь {review.author.get_full_name() or review.author.username} оставил отзыв об услуге '{service.name}' (автосервис '{service.autoservice.name}')"
                if order:
                    message_text += f" по заказу №{order.id}"
                message_text += f". Оценка: {review.rating}/5. Требуется модерация."
                
                for superadmin in superadmins:
                    add_notification(
                        user=superadmin,
                        title="Новый отзыв на модерацию",
                        message=message_text,
                        level="info"
                    )
            except Exception:
                pass  # Игнорируем ошибки уведомлений
            
            messages.success(request, 'Спасибо за отзыв! Он будет опубликован после модерации.')
            
            # Возвращаем на соответствующую страницу
            if order:
                return redirect('core:user_order_detail', order_id=order.id)
            else:
                return redirect('core:service_reviews_list', service_id=service.id)
    else:
        form = ServiceReviewForm(service=service)
    
    # Определяем заголовок в зависимости от контекста
    if order:
        title = f'Отзыв по заказу №{order.id} - услуга "{service.name}"'
    else:
        title = f'Отзыв об услуге {service.name}'
    
    context = {
        'form': form,
        'service': service,
        'order': order,
        'title': title
    }
    
    return render(request, 'core/reviews/review_create.html', context)


@login_required
@user_passes_test(lambda user: user.role in ['autoservice_admin', 'manager'])
def review_reply_create(request, review_id):
    """Создание ответа на отзыв"""
    review = get_object_or_404(Review, id=review_id, is_approved=True)
    
    # Проверяем права доступа
    user_autoservice = getattr(request.user, 'autoservice', None)
    if not user_autoservice:
        raise PermissionDenied('У вас нет доступа к этому действию')
    
    # Проверяем, что отзыв относится к автосервису пользователя
    review_autoservice = None
    if review.autoservice:
        review_autoservice = review.autoservice
    elif review.reviewed_user and hasattr(review.reviewed_user, 'autoservice'):
        review_autoservice = review.reviewed_user.autoservice
    elif review.service:
        review_autoservice = review.service.autoservice
    
    if review_autoservice != user_autoservice:
        raise PermissionDenied('У вас нет доступа к этому отзыву')
    
    # Проверяем, нет ли уже ответа
    if hasattr(review, 'reply'):
        messages.warning(request, 'На этот отзыв уже есть ответ')
        return redirect('core:autoservice_reviews_list', autoservice_id=review_autoservice.id)
    
    if request.method == 'POST':
        form = ReviewReplyForm(request.POST, review=review)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.author = request.user
            reply.save()
            
            messages.success(request, 'Ответ на отзыв добавлен')
            return redirect('core:autoservice_reviews_list', autoservice_id=review_autoservice.id)
    else:
        form = ReviewReplyForm(review=review)
    
    context = {
        'form': form,
        'review': review,
        'title': 'Ответ на отзыв'
    }
    
    return render(request, 'core/reviews/review_reply_create.html', context)


# ============== МОДЕРАЦИЯ ОТЗЫВОВ ==============

@login_required
@user_passes_test(is_super_admin)
def reviews_moderation(request):
    """Модерация отзывов для суперадминистратора"""
    # Получаем все отзывы с фильтрацией
    reviews_queryset = Review.objects.select_related(
        'author', 'autoservice', 'reviewed_user', 'service'
    ).order_by('-created_at')
    
    # Фильтры
    status_filter = request.GET.get('status')
    review_type_filter = request.GET.get('review_type')
    rating_filter = request.GET.get('rating')
    
    # Применяем фильтры статуса
    if status_filter == 'pending':
        reviews_queryset = reviews_queryset.filter(is_approved=False, is_rejected=False)
    elif status_filter == 'approved':
        reviews_queryset = reviews_queryset.filter(is_approved=True)
    elif status_filter == 'rejected':
        reviews_queryset = reviews_queryset.filter(is_rejected=True)
    else:
        # По умолчанию показываем только ожидающие модерации
        if not status_filter:
            reviews_queryset = reviews_queryset.filter(is_approved=False, is_rejected=False)
    
    # Фильтр по типу отзыва
    if review_type_filter == 'autoservice':
        reviews_queryset = reviews_queryset.filter(autoservice__isnull=False)
    elif review_type_filter == 'master':
        reviews_queryset = reviews_queryset.filter(reviewed_user__isnull=False)
    elif review_type_filter == 'service':
        reviews_queryset = reviews_queryset.filter(service__isnull=False)
    
    # Фильтр по рейтингу
    if rating_filter:
        reviews_queryset = reviews_queryset.filter(rating=rating_filter)
    
    reviews = reviews_queryset
    
    # Статистика
    pending_count = Review.objects.filter(is_approved=False, is_rejected=False).count()
    approved_count = Review.objects.filter(is_approved=True).count()
    rejected_count = Review.objects.filter(is_rejected=True).count()
    total_count = Review.objects.count()
    
    context = {
        'title': 'Модерация отзывов',
        'reviews': reviews,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'total_count': total_count,
    }
    
    return render(request, 'core/admin/reviews_moderation.html', context)


@login_required
@user_passes_test(is_super_admin)
@require_POST
def review_approve(request, review_id):
    """Одобрение отзыва"""
    review = get_object_or_404(Review, id=review_id, is_approved=False, is_rejected=False)
    
    review.is_approved = True
    review.is_rejected = False
    review.moderated_by = request.user
    from django.utils import timezone
    review.approved_at = timezone.now()
    review.moderated_at = timezone.now()
    review.save()
    
    # Уведомляем автора отзыва об одобрении
    try:
        target_name = ""
        if review.autoservice:
            target_name = f"автосервисе '{review.autoservice.name}'"
        elif review.reviewed_user:
            target_name = f"мастере '{review.reviewed_user.get_full_name() or review.reviewed_user.username}'"
        elif review.service:
            target_name = f"услуге '{review.service.name}'"
        
        add_notification(
            user=review.author,
            title="Отзыв одобрен",
            message=f"Ваш отзыв о {target_name} одобрен и опубликован.",
            level="success"
        )
    except Exception:
        pass
    
    messages.success(request, f'Отзыв №{review.id} одобрен')
    return redirect('core:reviews_moderation')


@login_required
@login_required
@user_passes_test(is_super_admin)
@require_POST
def review_reject(request, review_id):
    """Отклонение отзыва"""
    review = get_object_or_404(Review, id=review_id, is_approved=False, is_rejected=False)
    
    reject_reason = request.POST.get('reject_reason', '')
    
    review.is_rejected = True
    review.is_approved = False
    review.moderated_by = request.user
    from django.utils import timezone
    review.rejected_at = timezone.now()
    review.moderated_at = timezone.now()
    review.save()
    
    # Уведомляем автора отзыва об отклонении
    try:
        target_name = ""
        if review.autoservice:
            target_name = f"автосервисе '{review.autoservice.name}'"
        elif review.reviewed_user:
            target_name = f"мастере '{review.reviewed_user.get_full_name() or review.reviewed_user.username}'"
        elif review.service:
            target_name = f"услуге '{review.service.name}'"
        
        message = f"Ваш отзыв о {target_name} отклонен модератором."
        if reject_reason:
            message += f" Причина: {reject_reason}"
        
        add_notification(
            user=review.author,
            title="Отзыв отклонен",
            message=message,
            level="warning"
        )
    except Exception:
        pass
    
    messages.success(request, f'Отзыв №{review.id} отклонен')
    return redirect('core:reviews_moderation')


@login_required
def order_review_create(request, order_id):
    """Создание отзыва по завершенному заказу - перенаправляет на создание отзыва об услуге"""
    order = get_object_or_404(Order, id=order_id, client=request.user, status='completed')
    
    # Проверяем, не оставлен ли уже отзыв
    if order.review_left:
        messages.warning(request, 'Вы уже оставили отзыв по этому заказу')
        return redirect('core:user_order_detail', order_id=order.id)
    
    # Проверяем, что с момента завершения заказа прошло не более 30 дней
    from datetime import timedelta
    from django.utils import timezone
    if order.completed_at and order.completed_at < timezone.now() - timedelta(days=30):
        messages.error(request, 'Срок для оставления отзыва истёк (30 дней с момента завершения заказа)')
        return redirect('core:user_order_detail', order_id=order.id)
    
    # Перенаправляем на создание отзыва об услуге с параметром заказа
    from django.urls import reverse
    return redirect(f"{reverse('core:service_review_create', args=[order.service.id])}?order_id={order.id}")
