from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.db.models import Count
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from .models import Region, AutoService
from .forms import AutoServiceEditForm, AddManagerForm, AutoServiceRegistrationForm

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
        else:
            # Если автосервис неактивен, оставляем пользователя клиентом
            # Роль будет назначена администратором автосервиса позже
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
    """Проверка, является ли пользователь администратором автосервиса"""
    return (
        user.is_authenticated
        and user.role == "autoservice_admin"
        and user.autoservice is not None
        and user.autoservice.is_active  # Добавляем проверку активности автосервиса
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

    # Получаем только менеджеров автосервиса (исключаем администраторов)
    managers = (
        User.objects.filter(autoservice=autoservice, role="manager", is_active=True)
        .exclude(role="super_admin")
        .order_by("last_name", "first_name", "username")
    )

    # Статистика для шаблона
    total_managers = managers.count()
    active_managers = managers.filter(is_active=True).count()

    # Дополнительная статистика для информации
    all_staff = User.objects.filter(autoservice=autoservice).exclude(role="super_admin")
    admin_count = all_staff.filter(role="autoservice_admin").count()

    context = {
        "title": f"Менеджеры - {autoservice.name}",
        "autoservice": autoservice,
        "managers": managers,
        "total_managers": total_managers,
        "active_managers": active_managers,
        "manager_count": total_managers,  # Все в списке - менеджеры
        "admin_count": admin_count,  # Для информационной панели
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
                user.role = role  # Администратор автосервиса назначает роль напрямую
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


def activate_autoservice_users(autoservice):
    """Активирует пользователей автосервиса, восстанавливая их роли"""
    # Получаем всех пользователей, привязанных к автосервису, у которых есть сохраненная роль
    users = User.objects.filter(autoservice=autoservice, previous_role__isnull=False)

    activated_count = 0
    for user in users:
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
        # Сохраняем текущую роль в поле previous_role
        user.previous_role = user.role
        # Переводим в клиенты
        user.role = "client"
        user.save()
        deactivated_count += 1

    return deactivated_count


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
