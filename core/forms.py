from django import forms
from django.contrib.auth import get_user_model
from .models import AutoService, Region

User = get_user_model()


class AutoServiceEditForm(forms.ModelForm):
    """Форма редактирования автосервиса"""

    class Meta:
        model = AutoService
        fields = [
            "name",
            "region",
            "address",
            "phone",
            "email",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Название автосервиса",
                }
            ),
            "region": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Полный адрес автосервиса",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "+7 (XXX) XXX-XX-XX",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "email@autoservice.ru",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Краткое описание услуг и особенностей автосервиса",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }
        labels = {
            "name": "Название автосервиса",
            "region": "Регион",
            "address": "Адрес",
            "phone": "Телефон",
            "email": "Email",
            "description": "Описание",
            "is_active": "Автосервис активен",
        }


class AddManagerForm(forms.Form):
    """Форма добавления менеджера"""

    email = forms.EmailField(
        label="Email пользователя",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "user@example.com",
            }
        ),
        help_text="Введите email зарегистрированного пользователя",
    )

    role = forms.ChoiceField(
        label="Роль",
        choices=[
            ("manager", "Менеджер"),
            ("autoservice_admin", "Администратор автосервиса"),
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        initial="manager",
        help_text="Выберите роль для нового сотрудника",
    )

    def __init__(self, *args, **kwargs):
        self.autoservice = kwargs.pop("autoservice", None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise forms.ValidationError("Пользователь с таким email не найден")

        # Проверяем, не является ли пользователь уже сотрудником этого автосервиса
        if user.autoservice == self.autoservice:
            raise forms.ValidationError(
                "Пользователь уже является сотрудником данного автосервиса"
            )

        # Проверяем, не является ли пользователь сотрудником другого автосервиса
        if user.autoservice and user.autoservice != self.autoservice:
            raise forms.ValidationError(
                f'Пользователь уже работает в автосервисе "{user.autoservice.name}"'
            )

        # Проверяем, не является ли пользователь суперадминистратором
        if user.role == "super_admin":
            raise forms.ValidationError(
                "Нельзя назначить суперадминистратора менеджером автосервиса"
            )

        return email

    def get_user(self):
        """Возвращает пользователя по email из cleaned_data"""
        email = self.cleaned_data.get("email")
        if email:
            try:
                return User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:
                return None
        return None
