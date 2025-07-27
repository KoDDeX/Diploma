from django.urls import path
from .views import (
    LandingPageView,
    autoservice_detail_view,
    admin_panel_view,
    toggle_autoservice_status,
    get_users_for_manager,
    assign_manager,
    # Панель администратора автосервиса
    autoservice_admin_dashboard,
    autoservice_edit_profile,
    autoservice_managers_list,
    autoservice_add_manager,
    autoservice_remove_manager,
    autoservice_service_create,
    autoservice_services_list,
    # Регистрация автосервиса
    autoservice_register_view,
)
from django.conf import settings
from django.conf.urls.static import static

app_name = "core"

urlpatterns = [
    # Главная страница
    path("", LandingPageView.as_view(), name="landing"),
    # Регистрация автосервиса
    path(
        "register-autoservice/", autoservice_register_view, name="autoservice_register"
    ),
    # Панель управления для суперадминистратора
    path("admin-panel/", admin_panel_view, name="admin_panel"),
    path(
        "admin-panel/toggle-status/<int:autoservice_id>/",
        toggle_autoservice_status,
        name="toggle_autoservice_status",
    ),
    path(
        "admin-panel/get-users/<int:autoservice_id>/",
        get_users_for_manager,
        name="get_users_for_manager",
    ),
    path(
        "admin-panel/assign-manager/<int:autoservice_id>/<int:user_id>/",
        assign_manager,
        name="assign_manager",
    ),
    # Панель администратора автосервиса
    path(
        "autoservice-admin/",
        autoservice_admin_dashboard,
        name="autoservice_admin_dashboard",
    ),
    path(
        "autoservice-admin/edit-profile/",
        autoservice_edit_profile,
        name="autoservice_edit_profile",
    ),
    path(
        "autoservice-admin/managers/",
        autoservice_managers_list,
        name="autoservice_managers_list",
    ),
    path(
        "autoservice-admin/managers/add/",
        autoservice_add_manager,
        name="autoservice_add_manager",
    ),
    path(
        "autoservice-admin/managers/remove/<int:user_id>/",
        autoservice_remove_manager,
        name="autoservice_remove_manager",
    ),
    # Управление услугами
    path(
        "autoservice-admin/services/",
        autoservice_services_list,
        name="autoservice_services_list",
    ),
    path(
        "autoservice-admin/services/create/",
        autoservice_service_create,
        name="autoservice_service_create",
    ),
    # Детальная страница автосервиса
    path(
        "<slug:autoservice_slug>/", autoservice_detail_view, name="autoservice_detail"
    ),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
