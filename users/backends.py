from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailModelBackend(ModelBackend):
    """
    Бэкенд аутентификации, позволяющий входить только по email
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        if username is None or password is None:
            return

        try:
            # Ищем пользователя только по email
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            # Запускаем хеширование пароля для защиты от timing атак
            User().set_password(password)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
