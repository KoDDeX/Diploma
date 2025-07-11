from django.shortcuts import get_object_or_404
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.contrib.auth import login, get_user_model
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .forms import (
    UserLoginForm,
    UserRegisterForm,
    UserProfileUpdateForm,
    UserPasswordChangeForm,
    CustomSetPasswordForm,
    CustomPasswordResetForm,
)
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, UpdateView


User = get_user_model()


class CustomPasswordResetView(PasswordResetView):
    """Кастомная реализация сброса пароля."""

    template_name = "users/password_reset_form.html"
    email_template_name = "users/password_reset_email.html"
    success_url = reverse_lazy("users:password_reset_done")


class CustomPasswordResetDoneView(PasswordResetDoneView):
    """Кастомная реализация подтверждения сброса пароля."""

    template_name = "users/password_reset_done.html"


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Кастомная реализация подтверждения сброса пароля."""

    template_name = "users/password_reset_confirm.html"
    form_class = CustomSetPasswordForm
    success_url = reverse_lazy("users:password_reset_complete")


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """Кастомная реализация страницы успешного сброса пароля."""

    template_name = "users/password_reset_complete.html"


class UserRegisterView(CreateView):
    """Представление для регистрации новых пользователей."""

    form_class = UserRegisterForm
    template_name = "users/register.html"
    success_url = reverse_lazy("landing")

    def dispatch(self, request, *args, **kwargs):
        """Перенаправляет аутентифицированных пользователей на главную страницу."""
        if request.user.is_authenticated:
            return redirect("landing")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Обрабатывает валидную форму: сохраняет пользователя и выполняет автоматический вход."""
        response = super().form_valid(form)
        user = form.save()  # Получаем сохраненного пользователя из формы
        login(self.request, user)
        messages.success(
            self.request,
            f"Добро пожаловать, {user.username}! Регистрация прошла успешно.",
        )
        return response

    def form_invalid(self, form):
        """Обрабатывает невалидную форму: выводит сообщение об ошибке."""
        messages.error(
            self.request, "Пожалуйста, исправьте ошибки в форме регистрации."
        )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Добавляет заголовок страницы в контекст."""
        context = super().get_context_data(**kwargs)
        context["title"] = "Регистрация"
        return context


class UserLoginView(LoginView):
    """Представление для аутентификации пользователей."""

    template_name = "users/login.html"
    form_class = UserLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        """Определяет URL для перенаправления после успешного входа."""
        messages.success(self.request, f"С возвращением, {self.request.user.username}!")
        next_url = self.request.GET.get("next")
        return next_url or reverse_lazy("landing")

    def form_invalid(self, form):
        """Обрабатывает невалидную форму: выводит сообщение об ошибке."""
        messages.error(self.request, "Неверный email или пароль. Попробуйте снова.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Добавляет заголовок страницы в контекст."""
        context = super().get_context_data(**kwargs)
        context["title"] = "Вход"
        return context


class UserProfileDetailView(LoginRequiredMixin, DetailView):
    """
    Представление для отображения профиля пользователя с проверкой принадлежности пользователя
    """

    model = User
    template_name = "users/profile_detail.html"
    context_object_name = "user"
    slug_field = "username"  # Добавить эту строку
    slug_url_kwarg = "username"  # Добавить эту строку

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Профиль {self.object.username}"
        context["is_own_profile"] = self.request.user == self.object
        return context


class UserLogoutView(LogoutView):
    """
    Представление для выхода пользователей
    """

    next_page = reverse_lazy("landing")  # Перенаправление после выхода

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Если пользователь авторизован, выводим сообщение об успешном выходе
            messages.info(request, "Вы успешно вышли из системы.")
        return super().dispatch(request, *args, **kwargs)


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    """
    Представление для обновления профиля пользователя
    """

    model = User
    template_name = "users/profile_update_form.html"
    form_class = UserProfileUpdateForm
    slug_field = "username"
    slug_url_kwarg = "username"

    def get_object(self, queryset=None):
        """Получаем объект пользователя по username из URL"""
        username = self.kwargs.get("username")
        user = get_object_or_404(User, username=username)

        # Проверяем, что пользователь может редактировать этот профиль
        if user != self.request.user:
            raise PermissionDenied("Вы можете редактировать только свой профиль")

        return user

    def get_success_url(self):
        messages.success(self.request, "Ваш профиль успешно обновлен.")
        return reverse_lazy(
            "users:profile_detail", kwargs={"username": self.object.username}
        )

    def form_invalid(self, form):
        """Обрабатывает невалидную форму: выводит сообщение об ошибке."""
        messages.error(self.request, "Пожалуйста, исправьте ошибки в форме.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Редактирование профиля"
        return context


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """
    Представление для изменения пароля пользователя
    """

    form_class = UserPasswordChangeForm
    template_name = "users/password_change_form.html"

    def get_success_url(self):
        """Определяет URL для перенаправления после успешной смены пароля."""
        messages.success(self.request, "Ваш пароль был успешно изменен.")
        return reverse_lazy(
            "users:profile_detail", kwargs={"username": self.request.user.username}
        )

    def form_invalid(self, form):
        """Обрабатывает невалидную форму: выводит сообщение об ошибке."""
        messages.error(self.request, "Пожалуйста, исправьте ошибки при смене пароля.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Изменение пароля"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Ваш пароль успешно изменен.")
        return super().form_valid(form)
