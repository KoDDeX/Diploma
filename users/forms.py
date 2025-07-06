from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class HTML5DateInput(forms.DateInput):
    """Кастомный виджет для HTML5 date input"""

    input_type = "date"

    def format_value(self, value):
        """Принудительно форматируем дату в формате YYYY-MM-DD"""
        if value is None:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)


class UserRegisterForm(UserCreationForm):
    """
    Кастомная форма для регистрации пользователей
    """

    # Добавляем поле email тип EmailField
    email = forms.EmailField(
        label="Email",
        max_length=254,
        help_text="Введите ваш email",
        widget=forms.EmailInput(
            attrs={"class": "form-control mb-2", "placeholder": "Введите ваш email"}
        ),
        required=True,
    )

    class Meta:
        model = get_user_model()
        # Включаем username и email в форму регистрации
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control mb-2", "placeholder": "Имя пользователя"}
        )
        self.fields["password1"].widget.attrs.update(
            {"class": "form-control mb-2", "placeholder": "Придумайте пароль"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Повторите пароль"}
        )

        # Убираем helptext для полей формы
        for field_name in ("username", "password1", "password2", "email"):
            if self.fields.get(field_name):
                self.fields[field_name].help_text = None

    def save(self, commit=True):
        """
        Переопределяем метод save для корректного сохранения поля email
        """
        user = super().save(commit=commit)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            # Установка бэкенда для аутентификации
            user.backend = "django.contrib.auth.backends.ModelBackend"
        return user

    def clean_email(self):
        """
        Проверяем уникальность email
        """
        email = self.cleaned_data.get("email")
        if get_user_model().objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email


class UserLoginForm(AuthenticationForm):
    """Форма для входа пользователя в систему только по email."""

    def __init__(self, *args, **kwargs):
        """Инициализация формы входа: настройка полей."""
        super().__init__(*args, **kwargs)
        # Кастомизация поля username (но фактически это email)
        self.fields["username"].label = "Email"
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control mb-2",
                "placeholder": "Введите ваш email",
                "type": "email",  # HTML5 валидация email
            }
        )
        # Кастомизация поля password
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Пароль"}
        )


class UserProfileUpdateForm(forms.ModelForm):
    """
    Форма для редактирования профиля пользователя
    """

    class Meta:
        model = User
        fields = ["username", "email", "avatar", "birth_date"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "avatar": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": "images/*",
                }
            ),
            "birth_date": HTML5DateInput(attrs={"class": "form-control"}),
        }


class UserPasswordChangeForm(PasswordChangeForm):
    """
    Форма для изменения пароля пользователя
    """

    def __init__(self, *args, **kwargs):
        """Инициализация формы смены пароля: настройка полей и сброс подсказок."""
        super().__init__(*args, **kwargs)
        # Кастомизация поля старого пароля
        self.fields["old_password"].widget.attrs.update(
            {"class": "form-control mb-2", "placeholder": "Старый пароль"}
        )
        # Кастомизация поля нового пароля
        self.fields["new_password1"].widget.attrs.update(
            {"class": "form-control mb-2", "placeholder": "Новый пароль"}
        )
        # Кастомизация поля подтверждения пароля
        self.fields["new_password2"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Подтвердите новый пароль"}
        )
        # Сброс help_text для полей пароля
        for field_name in ("old_password", "new_password1", "new_password2"):
            if self.fields.get(field_name):
                # Сбрасываем подсказки (help_text)
                self.fields[field_name].help_text = ""
