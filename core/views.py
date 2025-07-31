from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.db.models import Count
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import PermissionDenied
from .models import Region, AutoService, Service, Order, Car, Notification
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

    context = {
        "title": f"{autoservice.name} - {autoservice.region.name}",
        "autoservice": autoservice,
        "services": services,
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
        form = OrderCreateForm(request.POST, service=service, user=request.user)
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
        form = OrderCreateForm(service=service, user=request.user)

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
    
    # Получаем доступных мастеров
    available_masters = User.objects.filter(
        autoservice=autoservice,
        role='master',
        is_active=True
    ).order_by('last_name', 'first_name', 'username')
    
    context = {
        'title': f'Заказ №{order.id} - {autoservice.name}',
        'autoservice': autoservice,
        'order': order,
        'available_masters': available_masters,
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
    """Назначение мастера на заказ"""
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
        
        # Проверяем, не занят ли мастер в это время
        conflicting_orders = Order.objects.filter(
            assigned_master=master,
            preferred_date=order.preferred_date,
            status__in=['confirmed', 'in_progress']
        ).exclude(id=order.id)
        
        if conflicting_orders.exists():
            messages.error(
                request,
                f"Мастер {master.get_full_name() or master.username} уже занят в это время другим заказом"
            )
            return redirect('core:autoservice_order_detail', order_id=order.id)
        
        # Назначаем мастера
        order.assigned_master = master
        order.save()
        
        # Создаем уведомления
        add_notification(
            user=master,
            title="Новое назначение",
            message=f"Вам назначен заказ №{order.id} на услугу '{order.service.name}' в автосервисе '{autoservice.name}' на {order.preferred_date.strftime('%d.%m.%Y')}.",
            level="info"
        )
        
        # Уведомляем администратора автосервиса о назначении
        if autoservice.admin != request.user:  # Если назначение делает не сам администратор
            add_notification(
                user=autoservice.admin,
                title="Назначен мастер",
                message=f"Заказ №{order.id} назначен мастеру {master.get_full_name() or master.username}. Клиент: {order.get_client_name()}.",
                level="info"
            )
        
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
    
    if order.assigned_master:
        add_notification(
            user=order.assigned_master,
            title="Заказ завершен",
            message=f"Заказ №{order.id} на услугу '{order.service.name}' успешно завершен.",
            level="success"
        )
    
    messages.success(request, f"Заказ №{order.id} завершен")
    
    return redirect('core:autoservice_order_detail', order_id=order.id)
