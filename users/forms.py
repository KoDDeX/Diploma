from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import get_user_model

User = get_user_model()


class UserRegisterForm(UserCreationForm):
    """Форма для регистрации нового пользователя."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control mb-2', 'placeholder': 'Email'}),
        required=True
    )

    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        """Инициализация формы входа: настройка полей."""
        super().__init__(*args, **kwargs)
        
        # Кастомизация поля username
        self.fields['username'].widget.attrs.update({
            'class': 'form-control mb-2',
            'placeholder': 'Имя пользователя',
        })
        # Кастомизация поля password1
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control mb-2',
            'placeholder': 'Придумайте пароль',
        })
        # Кастомизация поля password2
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Повторите пароль',
        })
        # Сбрасываем подсказки (help_text) для полей, чтобы не отображались
        for field_name in ('username', 'password1', 'password2'):
            if self.fields.get(field_name):
                # Сбрасываем подсказки (help_text)
                self.fields[field_name].help_text = ''
                

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