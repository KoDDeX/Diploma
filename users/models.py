from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.base_user import BaseUserManager


class User(AbstractUser):
    # Отключаем стандартные поля, чтобы переопределить их
    # first_name = None
    # last_name = None

    # Переопределяем поля с русскими verbose_name
    first_name = models.CharField(max_length=150, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Фамилия")

    email = models.EmailField(
        unique=True, verbose_name="Email"
    )  # Делаем email уникальным и обязательным для логина

    avatar = models.ImageField(
        upload_to="users/avatars/", null=True, blank=True, verbose_name="Аватар"
    )
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    telegram_id = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Telegram ID"
    )
    github_id = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="GitHub ID"
    )

    # Указываем, что для логина будет использоваться поле email
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = [
        "username",
        "first_name",
        "last_name",
    ]  # Добавляем имя и фамилию в обязательные поля при создании superuser

    def __str__(self):
        return self.email  # Или self.username, если предпочитаете

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ['email']


class UserManager(BaseUserManager):
    use_in_migrations = True
 
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password) # <-- критично
        user.save(using=self._db)
        return user
 
    def create_user(self, email, password=None, **extra_fields):
            extra_fields.setdefault("is_staff", False)
            extra_fields.setdefault("is_superuser", False)
            return self._create_user(email, password, **extra_fields)
 
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
 
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
 
        return self._create_user(email, password, **extra_fields)