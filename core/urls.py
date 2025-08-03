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
    autoservice_service_edit,
    autoservice_service_toggle,
    autoservice_service_delete,
    # Управление заказами автосервиса
    autoservice_orders_list,
    autoservice_order_detail,
    autoservice_order_assign_master,
    autoservice_order_confirm,
    autoservice_order_cancel,
    autoservice_order_start,
    autoservice_order_complete,
    # Панель загрузки мастеров
    autoservice_workload_view,
    # Управление графиками работы
    work_schedule_list,
    work_schedule_create,
    work_schedule_edit,
    work_schedule_delete,
    # Регистрация автосервиса
    autoservice_register_view,
    # Система заказов
    order_create,
    order_success,
    check_masters_availability,
    get_available_time_slots,
    # Управление автомобилями пользователя
    user_cars_list,
    # Управление автомобилями пользователя
    user_car_add,
    user_car_edit,
    user_car_delete,
    user_car_set_default,
    # Управление заказами пользователя
    user_orders_list,
    user_order_detail,
    user_order_cancel,
    # Уведомления
    notifications_list,
    notification_mark_read,
    notification_delete,
    notification_get_count,
    notification_get_recent,
    # Система отзывов
    autoservice_reviews_list,
    autoservice_review_create,
    master_reviews_list,
    master_review_create,
    service_reviews_list,
    service_review_create,
    review_reply_create,
    # Модерация отзывов для суперадминистратора
    reviews_moderation,
    review_approve,
    review_reject,
    # Отзыв по заказу
    order_review_create,
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
    path(
        "autoservice-admin/services/edit/<int:service_id>/",
        autoservice_service_edit,
        name="autoservice_service_edit",
    ),
    path(
        "autoservice-admin/services/toggle/<int:service_id>/",
        autoservice_service_toggle,
        name="autoservice_service_toggle",
    ),
    path(
        "autoservice-admin/services/delete/<int:service_id>/",
        autoservice_service_delete,
        name="autoservice_service_delete",
    ),
    # Управление заказами автосервиса
    path(
        "autoservice-admin/orders/",
        autoservice_orders_list,
        name="autoservice_orders_list",
    ),
    path(
        "autoservice-admin/orders/<int:order_id>/",
        autoservice_order_detail,
        name="autoservice_order_detail",
    ),
    path(
        "autoservice-admin/orders/<int:order_id>/assign-master/",
        autoservice_order_assign_master,
        name="autoservice_order_assign_master",
    ),
    path(
        "autoservice-admin/orders/<int:order_id>/confirm/",
        autoservice_order_confirm,
        name="autoservice_order_confirm",
    ),
    path(
        "autoservice-admin/orders/<int:order_id>/cancel/",
        autoservice_order_cancel,
        name="autoservice_order_cancel",
    ),
    path(
        "autoservice-admin/orders/<int:order_id>/start/",
        autoservice_order_start,
        name="autoservice_order_start",
    ),
    path(
        "autoservice-admin/orders/<int:order_id>/complete/",
        autoservice_order_complete,
        name="autoservice_order_complete",
    ),
    # Панель загрузки мастеров
    path(
        "autoservice-admin/workload/",
        autoservice_workload_view,
        name="autoservice_workload",
    ),
    # Управление автомобилями пользователя
    path(
        "my-cars/",
        user_cars_list,
        name="user_cars_list",
    ),
    path(
        "my-cars/add/",
        user_car_add,
        name="user_car_add",
    ),
    path(
        "my-cars/edit/<int:car_id>/",
        user_car_edit,
        name="user_car_edit",
    ),
    path(
        "my-cars/delete/<int:car_id>/",
        user_car_delete,
        name="user_car_delete",
    ),
    path(
        "my-cars/set-default/<int:car_id>/",
        user_car_set_default,
        name="user_car_set_default",
    ),
    # Управление заказами пользователя
    path(
        "my-orders/",
        user_orders_list,
        name="user_orders_list",
    ),
    path(
        "my-orders/<int:order_id>/",
        user_order_detail,
        name="user_order_detail",
    ),
    path(
        "my-orders/<int:order_id>/cancel/",
        user_order_cancel,
        name="user_order_cancel",
    ),
    # Уведомления
    path("notifications/", notifications_list, name="notifications_list"),
    path(
        "notifications/<int:notification_id>/mark-read/",
        notification_mark_read,
        name="notification_mark_read",
    ),
    path(
        "notifications/<int:notification_id>/delete/",
        notification_delete,
        name="notification_delete",
    ),
    path(
        "api/notifications/count/",
        notification_get_count,
        name="notification_get_count",
    ),
    path(
        "api/notifications/recent/",
        notification_get_recent,
        name="notification_get_recent",
    ),
    # Управление графиками работы
    path(
        "autoservice-admin/work-schedule/",
        work_schedule_list,
        name="work_schedule_list",
    ),
    path(
        "autoservice-admin/work-schedule/create/",
        work_schedule_create,
        name="work_schedule_create",
    ),
    path(
        "autoservice-admin/work-schedule/edit/<int:schedule_id>/",
        work_schedule_edit,
        name="work_schedule_edit",
    ),
    path(
        "autoservice-admin/work-schedule/delete/<int:schedule_id>/",
        work_schedule_delete,
        name="work_schedule_delete",
    ),
    # Детальная страница автосервиса (должна быть последней среди обычных маршрутов)
    path(
        "<slug:autoservice_slug>/", autoservice_detail_view, name="autoservice_detail"
    ),
    # Система заказов
    path(
        "autoservice/<int:autoservice_id>/service/<int:service_id>/order/",
        order_create,
        name="order_create",
    ),
    path(
        "order/<int:order_id>/success/",
        order_success,
        name="order_success",
    ),
    # API для проверки доступности мастеров
    path(
        "api/autoservice/<int:autoservice_id>/check-masters-availability/",
        check_masters_availability,
        name="check_masters_availability",
    ),
    # API для получения доступных временных слотов
    path(
        "api/autoservice/<int:autoservice_id>/available-time-slots/",
        get_available_time_slots,
        name="get_available_time_slots",
    ),
    # Система отзывов
    path(
        "autoservice/<int:autoservice_id>/reviews/",
        autoservice_reviews_list,
        name="autoservice_reviews_list",
    ),
    path(
        "autoservice/<int:autoservice_id>/review/create/",
        autoservice_review_create,
        name="autoservice_review_create",
    ),
    path(
        "master/<int:master_id>/reviews/",
        master_reviews_list,
        name="master_reviews_list",
    ),
    path(
        "master/<int:master_id>/review/create/",
        master_review_create,
        name="master_review_create",
    ),
    path(
        "service/<int:service_id>/reviews/",
        service_reviews_list,
        name="service_reviews_list",
    ),
    path(
        "service/<int:service_id>/review/create/",
        service_review_create,
        name="service_review_create",
    ),
    path(
        "review/<int:review_id>/reply/",
        review_reply_create,
        name="review_reply_create",
    ),
    # Модерация отзывов для суперадминистратора
    path(
        "admin-panel/reviews-moderation/",
        reviews_moderation,
        name="reviews_moderation",
    ),
    path(
        "admin-panel/review-approve/<int:review_id>/",
        review_approve,
        name="review_approve",
    ),
    path(
        "admin-panel/review-reject/<int:review_id>/",
        review_reject,
        name="review_reject",
    ),
    # Отзыв по заказу
    path(
        "order/<int:order_id>/review/create/",
        order_review_create,
        name="order_review_create",
    ),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
