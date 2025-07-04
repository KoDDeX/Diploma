from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import UserLoginForm

# Create your views here.
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
        messages.error(
            self.request, "Неверное имя пользователя или пароль. Попробуйте снова."
        )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Добавляет заголовок страницы в контекст."""
        context = super().get_context_data(**kwargs)
        context["title"] = "Вход"
        return context