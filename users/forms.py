from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import get_user_model

User = get_user_model()

class UserLoginForm(AuthenticationForm):
    """Форма для входа пользователя в систему."""
    def __init__(self, *args, **kwargs):
        """Инициализация формы входа: настройка полей."""
        super().__init__(*args, **kwargs)
        # Кастомизация поля username
        self.fields['username'].widget.attrs.update({
            'class': 'form-control mb-2',
            'placeholder': 'Имя пользователя или email'
        })
        # Кастомизация поля password
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Пароль'
        })