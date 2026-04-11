import random
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDTimestampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def _default_reservation_code() -> str:
    return f"{random.randint(0, 9999):04d}"


class User(AbstractUser, TimestampMixin):
    class Role(models.TextChoices):
        BUYER = 'buyer', 'Покупатель'
        MANAGER = 'manager', 'Управляющий магазина'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        'Роль',
        max_length=20,
        choices=Role.choices,
        default=Role.BUYER,
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


class Store(UUIDTimestampedModel):
    name = models.CharField('Название', max_length=255)
    city = models.CharField('Город', max_length=128, blank=True, db_index=True)
    address = models.TextField('Адрес')
    latitude = models.DecimalField(
        'Широта',
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(Decimal('-90')),
            MaxValueValidator(Decimal('90')),
        ],
    )
    longitude = models.DecimalField(
        'Долгота',
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(Decimal('-180')),
            MaxValueValidator(Decimal('180')),
        ],
    )
    phone = models.CharField('Телефон', max_length=32)
    working_hours = models.CharField('Часы работы', max_length=255, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Управляющий',
        on_delete=models.PROTECT,
        related_name='managed_stores',
        limit_choices_to={'role': User.Role.MANAGER},
    )

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'

    def __str__(self) -> str:
        return self.name


class Category(UUIDTimestampedModel):
    name = models.CharField('Название', max_length=255)
    slug = models.SlugField('Код в адресе', max_length=255, unique=True, db_index=True)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class DefectType(UUIDTimestampedModel):
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Тип дефекта'
        verbose_name_plural = 'Типы дефектов'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Product(UUIDTimestampedModel):
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'В продаже'
        RESERVED = 'reserved', 'Забронирован'
        SOLD = 'sold', 'Продан'
        ARCHIVED = 'archived', 'В архиве'

    title = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    price_original = models.DecimalField('Цена без скидки', max_digits=10, decimal_places=2)
    price_discounted = models.DecimalField('Цена со скидкой', max_digits=10, decimal_places=2)
    defect_type = models.ForeignKey(
        DefectType,
        verbose_name='Тип дефекта',
        on_delete=models.PROTECT,
        related_name='products',
    )
    store = models.ForeignKey(
        Store,
        verbose_name='Магазин',
        on_delete=models.CASCADE,
        related_name='products',
    )
    category = models.ForeignKey(
        Category,
        verbose_name='Категория',
        on_delete=models.PROTECT,
        related_name='products',
    )
    photos = models.JSONField('Фотографии', default=list, blank=True)
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True,
    )

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.title


class Reservation(UUIDTimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Активна'
        COMPLETED = 'completed', 'Завершена'
        CANCELLED = 'cancelled', 'Отменена'
        EXPIRED = 'expired', 'Истекла'

    product = models.ForeignKey(
        Product,
        verbose_name='Товар',
        on_delete=models.CASCADE,
        related_name='reservations',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Покупатель',
        on_delete=models.CASCADE,
        related_name='reservations',
    )
    code = models.CharField(
        'Код брони',
        max_length=4,
        default=_default_reservation_code,
        validators=[RegexValidator(r'^\d{4}$', message='Код должен состоять из 4 цифр.')],
    )
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    expires_at = models.DateTimeField('Действует до')
    visit_time = models.DateTimeField('Время визита', null=True, blank=True)
    contact_phone = models.CharField('Телефон для связи', max_length=32, blank=True)
    contact_email = models.EmailField('Электронная почта', blank=True)

    class Meta:
        verbose_name = 'Бронь'
        verbose_name_plural = 'Брони'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.code} — {self.product_id}'
