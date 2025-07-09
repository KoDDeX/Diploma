from django.urls import path
from .views import *

app_name = "users"

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("register/", UserRegisterView.as_view(), name="register"),
    path(
        "profile/<str:username>/",
        UserProfileDetailView.as_view(),
        name="profile_detail",
    ),
    path(
        "profile/<str:username>/edit/",
        UserProfileUpdateView.as_view(),
        name="profile_edit",
    ),
    path("password_change/", UserPasswordChangeView.as_view(), name="password_change"),
    path("password-reset/", CustomPasswordResetView.as_view(), name="password_reset"),
    path(
        "password-reset/done/",
        CustomPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        CustomPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
