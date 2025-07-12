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


class UserProfileUpdateForm(forms.ModelForm):
    """Форма для редактирования профиля пользователя"""

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "birth_date",
            "avatar",
        )
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "birth_date": HTML5DateInput(attrs={"class": "form-control"}),
            "avatar": forms.FileInput(attrs={"class": "form-control"}),
        }


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

    # Добавляем поля имени и фамилии
    first_name = forms.CharField(
        label="Имя",
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control mb-2", "placeholder": "Введите ваше имя"}
        ),
        required=False,
    )

    last_name = forms.CharField(
        label="Фамилия",
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control mb-2", "placeholder": "Введите вашу фамилию"}
        ),
        required=False,
    )

    class Meta:
        model = get_user_model()
        # Включаем все основные поля в форму регистрации
        fields = ("username", "email", "first_name", "last_name")

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
        for field_name in (
            "username",
            "password1",
            "password2",
            "email",
            "first_name",
            "last_name",
        ):
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


class CustomPasswordResetForm(PasswordResetForm):
    """Кастомная форма для сброса пароля."""

    def __init__(self, *args, **kwargs):
        """Инициализация формы сброса пароля: настройка полей."""
        super().__init__(*args, **kwargs)
        # Кастомизация поля email
        self.fields["email"].widget.attrs.update(
            {"class": "form-control mb-2", "placeholder": "Email"}
        )


class CustomSetPasswordForm(SetPasswordForm):
    """Кастомная форма для сброса пароля."""

    def __init__(self, *args, **kwargs):
        """Инициализация формы сброса пароля: настройка полей."""
        super().__init__(*args, **kwargs)
        # Кастомизация поля new_password1
        self.fields["new_password1"].widget.attrs.update(
            {"class": "form-control mb-2", "placeholder": "Новый пароль"}
        )
        # Кастомизация поля new_password2
        self.fields["new_password2"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Подтвердите новый пароль"}
        )

        # Сброс help_text для полей пароля
        for field_name in ("new_password1", "new_password2"):
            if self.fields.get(field_name):
                # Сбрасываем подсказки (help_text)
                self.fields[field_name].help_text = ""


class AutoServiceUserForm(forms.ModelForm):
    """
    Форма для создания/редактирования пользователей автосервиса (менеджеров)
    Используется администраторами автосервисов
    """

    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=False,
        help_text="Оставьте пустым, если не хотите менять пароль",
    )

    password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=False,
        help_text="Введите тот же пароль для подтверждения",
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "role", "is_active"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.autoservice = kwargs.pop("autoservice", None)
        super().__init__(*args, **kwargs)

        # Ограничиваем выбор ролей для администратора автосервиса
        self.fields["role"].choices = [
            ("manager", "Менеджер"),
            ("client", "Клиент"),
        ]

        # Делаем поля обязательными
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

        # Если редактируем существующего пользователя
        if self.instance.pk:
            self.fields["password1"].help_text = (
                "Оставьте пустым, если не хотите менять пароль"
            )
        else:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
            self.fields["password1"].help_text = (
                "Введите пароль для нового пользователя"
            )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError("Пароли не совпадают")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)

        # Привязываем к автосервису
        if self.autoservice:
            user.autoservice = self.autoservice

        # Устанавливаем пароль, если он был введен
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)

        if commit:
            user.save()
        return user
