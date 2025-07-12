from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.urls import reverse


class Region(models.Model):
    """Регионы (города/области)"""

    name = models.CharField(max_length=100, verbose_name="Название региона")
    slug = models.SlugField(unique=True, verbose_name="Слаг для URL")
    is_active = models.BooleanField(default=False, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"

    def __str__(self):
        return f"{self.name}"


class AutoService(models.Model):
    """Автосервисы"""

    name = models.CharField(max_length=200, verbose_name="Название автосервиса")
    slug = models.SlugField(verbose_name="Слаг для URL")
    region = models.ForeignKey(Region, on_delete=models.CASCADE, verbose_name="Регион")
    address = models.TextField(verbose_name="Адрес")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(verbose_name="Email")
    description = models.TextField(blank=True, verbose_name="Описание")
    logo = models.ImageField(upload_to="autoservices/logos/", blank=True)
    is_active = models.BooleanField(default=False, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Автосервис"
        verbose_name_plural = "Автосервисы"
        unique_together = [["region", "slug"]]  # Уникальность в рамках региона

    def __str__(self):
        return f"{self.name} ({self.region.name})"


class UserManager(BaseUserManager):
    """Менеджер для кастомной модели пользователя"""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)

        # Если username не задан, генерируем его из email
        if not extra_fields.get("username"):
            extra_fields["username"] = email

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", "client")
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "super_admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Расширенная модель пользователя"""

    ROLE_CHOICES = [
        ("super_admin", "Главный администратор"),
        ("autoservice_admin", "Администратор автосервиса"),
        ("manager", "Менеджер"),
        ("client", "Клиент"),
    ]

    # Отключаем стандартные поля, чтобы переопределить их
    first_name = None
    last_name = None

    # Переопределяем поля с русскими verbose_name
    first_name = models.CharField(max_length=150, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Фамилия")
    email = models.EmailField(unique=True, verbose_name="Email")
    avatar = models.ImageField(
        upload_to="users/avatars/",
        default="users/avatars/default.jpg",
        blank=True,
        verbose_name="Аватар",
    )
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="client", verbose_name="Роль"
    )
    autoservice = models.ForeignKey(
        AutoService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Автосервис",
    )
    # phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")

    # Указываем, что для логина будет использоваться поле email
    USERNAME_FIELD = "email"
    # Добавляем имя и фамилию в обязательные поля при создании superuser
    REQUIRED_FIELDS = [
        "username",
        "first_name",
        "last_name",
    ]

    # Привязываем кастомный менеджер
    objects = UserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["email"]

    def can_manage_autoservice(self, autoservice):
        """Может ли управлять автосервисом"""
        if self.role == "super_admin":
            return True
        if self.role in ["autoservice_admin", "manager"]:
            return self.autoservice == autoservice
        return False

    def __str__(self):
        return self.email  # Или self.username

    def get_absolute_url(self):
        """Возвращает URL профиля пользователя"""
        return reverse("users:profile_detail", kwargs={"username": self.username})

    def save(self, *args, **kwargs):
        """Автоматически управляем флагом is_staff в зависимости от роли"""
        if self.role in ["super_admin", "autoservice_admin", "manager"]:
            self.is_staff = True
        elif self.role == "client":
            self.is_staff = False
            self.autoservice = None  # У клиента не может быть автосервиса

        super().save(*args, **kwargs)
