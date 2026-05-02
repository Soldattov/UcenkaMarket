import random
import logging  # ← НОВОЕ
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import LoginForm, ProductForm, RegisterForm
from .models import Category, DefectType, Product, Reservation, Store, User
from .nominatim import address_suggestions
from .product_files import save_product_uploads, validate_product_image_files
from .russian_cities import RUSSIAN_CITIES
from .session_auth import get_session_user, login_session
from .services.bitrix24 import send_reservation_to_bitrix24  # ← НОВОЕ

RESERVATION_HOLD = timedelta(hours=24)


def _reserve_context(
    product,
    *,
    can_reserve,
    visit_min,
    visit_max,
    contact_phone,
    contact_email,
    visit_time_value,
):
    return {
        'product': product,
        'can_reserve': can_reserve,
        'visit_min': visit_min,
        'visit_max': visit_max,
        'contact_phone': contact_phone,
        'contact_email': contact_email,
        'visit_time_value': visit_time_value,
    }


def _visit_time_bounds_local():
    """Границы для datetime-local и проверки (локальное время пользователя по настройкам Django)."""
    now = timezone.localtime(timezone.now())
    max_dt = now + RESERVATION_HOLD
    fmt = '%Y-%m-%dT%H:%M'
    return now.strftime(fmt), max_dt.strftime(fmt), timezone.now(), timezone.now() + RESERVATION_HOLD


def _post_auth_redirect(user):
    """После входа/регистрации менеджера ведём в кабинет, покупателя — в каталог."""
    if user.role == User.Role.MANAGER:
        return redirect(reverse('core:manager_cabinet'))
    return redirect(reverse('core:catalog'))


def _can_access_manager_area(user):
    """Менеджер магазина или пользователь админки Django (staff / superuser)."""
    return bool(
        user.role == User.Role.MANAGER
        or user.is_superuser
        or user.is_staff
    )


def _is_global_admin(user):
    return bool(user.is_superuser or user.is_staff)


def _store_manager_for_new_store(user):
    """Владелец записи Store при вводе названия с клавиатуры."""
    if user.role == User.Role.MANAGER:
        return user
    return (
        User.objects.filter(role=User.Role.MANAGER).order_by('date_joined').first()
        or user
    )


def _parse_geo_decimal(raw):
    """Широта/долгота из скрытых полей формы; при ошибке — None."""
    s = (raw or '').strip().replace(',', '.')
    if not s:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def session_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if get_session_user(request) is None:
            return redirect(reverse('core:index'))
        return view_func(request, *args, **kwargs)

    return _wrapped


def manager_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = get_session_user(request)
        if user is None:
            return redirect(reverse('core:index'))
        if not _can_access_manager_area(user):
            messages.warning(
                request,
                'Доступ только для управляющего магазина или администратора.',
            )
            return redirect(reverse('core:catalog'))
        return view_func(request, *args, **kwargs)

    return _wrapped


@require_http_methods(['GET', 'POST'])
def logout(request):
    request.session.flush()
    messages.info(request, 'Вы вышли из системы.')
    return redirect(reverse('core:index'))


@require_http_methods(['GET', 'POST'])
def index(request):
    login_form = LoginForm()
    register_form = RegisterForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'login':
            login_form = LoginForm(request.POST)
            if login_form.is_valid():
                phone = login_form.cleaned_data['phone'].strip()
                password = login_form.cleaned_data['password']
                user = authenticate(
                    request,
                    username=phone,
                    password=password,
                )
                if user is not None:
                    login_session(request, user)
                    messages.success(request, f'Добро пожаловать, {user.first_name or user.username}!')
                    return _post_auth_redirect(user)
                login_form.add_error(None, 'Неверный телефон или пароль.')
        elif action == 'register':
            register_form = RegisterForm(request.POST)
            if register_form.is_valid():
                cd = register_form.cleaned_data
                phone = cd['phone'].strip()
                try:
                    with transaction.atomic():
                        User.objects.create_user(
                            username=phone,
                            password=cd['password'],
                            first_name=cd['first_name'].strip(),
                            email=cd['email'].strip(),
                            role=cd['role'],
                        )
                except IntegrityError:
                    register_form.add_error(
                        'phone',
                        'Этот номер уже зарегистрирован. Войдите с паролём.',
                    )
                else:
                    user = authenticate(
                        request,
                        username=phone,
                        password=cd['password'],
                    )
                    if user is not None:
                        login_session(request, user)
                        messages.success(request, 'Регистрация прошла успешно.')
                        return _post_auth_redirect(user)
        else:
            messages.error(request, 'Выберите «Вход» или «Регистрация».')

    return render(
        request,
        'index.html',
        {'login_form': login_form, 'register_form': register_form},
    )


@session_login_required
@require_GET
def catalog(request):
    qs = Product.objects.filter(status=Product.Status.AVAILABLE).select_related(
        'store', 'category', 'defect_type'
    )

    category_id = request.GET.get('category')
    store_id = request.GET.get('store')
    defect_type_id = request.GET.get('defect_type')
    city = (request.GET.get('city') or '').strip()
    sort = (request.GET.get('sort') or 'new').strip()
    if sort not in ('new', 'city', 'city_desc', 'price', 'price_desc'):
        sort = 'new'
    q = (request.GET.get('q') or '').strip()

    if category_id:
        qs = qs.filter(category_id=category_id)
    if store_id:
        qs = qs.filter(store_id=store_id)
    if defect_type_id:
        qs = qs.filter(defect_type_id=defect_type_id)
    if city:
        qs = qs.filter(store__city=city)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    if sort == 'city':
        qs = qs.order_by('store__city', 'store__name', '-created_at')
    elif sort == 'city_desc':
        qs = qs.order_by('-store__city', 'store__name', '-created_at')
    elif sort == 'price':
        qs = qs.order_by('price_discounted', '-created_at')
    elif sort == 'price_desc':
        qs = qs.order_by('-price_discounted', '-created_at')
    else:
        qs = qs.order_by('-created_at')

    cities = (
        Store.objects.filter(products__status=Product.Status.AVAILABLE)
        .exclude(city='')
        .values_list('city', flat=True)
        .distinct()
        .order_by('city')
    )

    context = {
        'products': qs,
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'stores': Store.objects.order_by('name'),
        'defect_types': DefectType.objects.filter(is_active=True).order_by('name'),
        'catalog_cities': list(cities),
        'filters': {
            'category': category_id or '',
            'store': store_id or '',
            'defect_type': defect_type_id or '',
            'city': city,
            'sort': sort,
            'q': q,
        },
    }
    return render(request, 'catalog.html', context)


@session_login_required
@require_GET
def product_detail(request, id):  # noqa: A002
    product = get_object_or_404(
        Product.objects.select_related('store', 'category', 'defect_type'),
        pk=id,
    )
    return render(
        request,
        'product_detail.html',
        {
            'product': product,
            'can_reserve': product.status == Product.Status.AVAILABLE,
        },
    )


@session_login_required
@require_http_methods(['GET', 'POST'])
def reserve(request, id):  # noqa: A002
    user = get_session_user(request)
    product = get_object_or_404(
        Product.objects.select_related('store', 'category', 'defect_type'),
        pk=id,
    )
    visit_min, visit_max, now_utc, visit_latest_utc = _visit_time_bounds_local()

    if request.method == 'GET':
        return render(
            request,
            'reserve.html',
            _reserve_context(
                product,
                can_reserve=product.status == Product.Status.AVAILABLE,
                visit_min=visit_min,
                visit_max=visit_max,
                contact_phone=(user.username or '').strip(),
                contact_email=(user.email or '').strip(),
                visit_time_value='',
            ),
        )

    if product.status != Product.Status.AVAILABLE:
        messages.error(request, 'Этот товар нельзя забронировать.')
        return redirect(reverse('core:product_detail', kwargs={'id': id}))

    contact_phone = (request.POST.get('contact_phone') or '').strip()
    contact_email = (request.POST.get('contact_email') or '').strip()

    def _render_reserve_error(visit_time_value=''):
        return render(
            request,
            'reserve.html',
            _reserve_context(
                product,
                can_reserve=True,
                visit_min=visit_min,
                visit_max=visit_max,
                contact_phone=contact_phone,
                contact_email=contact_email,
                visit_time_value=visit_time_value,
            ),
        )

    if not request.POST.get('accept_rules'):
        messages.error(request, 'Нужно согласиться с правилами бронирования.')
        return _render_reserve_error((request.POST.get('visit_time') or '').strip())

    if not contact_phone:
        messages.error(request, 'Укажите номер телефона для связи.')
        return _render_reserve_error((request.POST.get('visit_time') or '').strip())
    if not contact_email:
        messages.error(request, 'Укажите электронную почту.')
        return _render_reserve_error((request.POST.get('visit_time') or '').strip())
    try:
        EmailValidator()(contact_email)
    except DjangoValidationError:
        messages.error(request, 'Введите корректный адрес электронной почты.')
        return _render_reserve_error((request.POST.get('visit_time') or '').strip())

    visit_raw = (request.POST.get('visit_time') or '').strip()
    visit_time = parse_datetime(visit_raw) if visit_raw else None
    if visit_time is not None and timezone.is_naive(visit_time):
        visit_time = timezone.make_aware(visit_time, timezone.get_current_timezone())

    if visit_time is not None:
        if visit_time < now_utc:
            messages.error(request, 'Время визита не может быть в прошлом.')
            return _render_reserve_error(visit_raw)
        if visit_time > visit_latest_utc:
            messages.error(
                request,
                'Время визита можно выбрать не дальше чем на 24 часа от текущего момента.',
            )
            return _render_reserve_error(visit_raw)

    expires_at = timezone.now() + RESERVATION_HOLD
    code = f'{random.randint(0, 9999):04d}'

    try:
        with transaction.atomic():
            locked = Product.objects.select_for_update().get(pk=product.pk)
            if locked.status != Product.Status.AVAILABLE:
                raise ValueError('unavailable')
            Reservation.objects.create(
                product=locked,
                user=user,
                code=code,
                status=Reservation.Status.ACTIVE,
                expires_at=expires_at,
                visit_time=visit_time,
                contact_phone=contact_phone,
                contact_email=contact_email,
            )
            locked.status = Product.Status.RESERVED
            locked.save(update_fields=['status', 'updated_at'])
    except ValueError:
        messages.error(request, 'Товар уже недоступен для брони.')
        return redirect(reverse('core:product_detail', kwargs={'id': id}))

    # === Отправка в Bitrix24 ===
    try:
        reservation = Reservation.objects.get(code=code, user=user, product=product)
        send_reservation_to_bitrix24(reservation)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send reservation {code} to Bitrix24: {e}")
    # ============================

    messages.success(
        request,
        f'Бронь создана. Код: {code}. Покажите его в магазине до {expires_at:%d.%m %H:%M}.',
    )
    return redirect(reverse('core:buyer_cabinet'))


@session_login_required
@require_GET
def buyer_cabinet(request):
    user = get_session_user(request)
    reservations = (
        Reservation.objects.filter(user=user, status=Reservation.Status.ACTIVE)
        .select_related('product', 'product__store')
        .order_by('-created_at')
    )
    return render(
        request,
        'buyer_cabinet.html',
        {'reservations': reservations},
    )


@manager_required
@require_GET
def manager_cabinet(request):
    user = get_session_user(request)
    if _is_global_admin(user):
        products = (
            Product.objects.select_related('store', 'category')
            .order_by('-created_at')
        )
        reservations = (
            Reservation.objects.select_related('product', 'user')
            .order_by('-created_at')
        )
    else:
        products = (
            Product.objects.filter(store__manager=user)
            .select_related('store', 'category')
            .order_by('-created_at')
        )
        reservations = (
            Reservation.objects.filter(product__store__manager=user)
            .select_related('product', 'user')
            .order_by('-created_at')
        )
    return render(
        request,
        'manager_cabinet.html',
        {'products': products, 'reservations': reservations},
    )


@manager_required
@require_http_methods(['GET', 'POST'])
def seller_add(request):
    manager = get_session_user(request)

    if request.method == 'POST':
        form = ProductForm(request.POST)
        files = [
            request.FILES.get('image_main'),
            request.FILES.get('image_extra1'),
            request.FILES.get('image_extra2'),
        ]
        img_err = validate_product_image_files(files)
        ok = form.is_valid()
        if img_err:
            form.add_error(None, img_err)
        if ok and not img_err:
            store_name = form.cleaned_data['store_name']
            store_city = form.cleaned_data['store_city']
            store_address = form.cleaned_data['store_address']
            lat = _parse_geo_decimal(request.POST.get('geo_lat'))
            lon = _parse_geo_decimal(request.POST.get('geo_lon'))
            if lat is None or lat < Decimal('-90') or lat > Decimal('90'):
                lat = Decimal('0')
            if lon is None or lon < Decimal('-180') or lon > Decimal('180'):
                lon = Decimal('0')
            store_mgr = _store_manager_for_new_store(manager)
            try:
                with transaction.atomic():
                    store, created = Store.objects.get_or_create(
                        name=store_name,
                        manager=store_mgr,
                        city=store_city,
                        defaults={
                            'address': store_address,
                            'latitude': lat,
                            'longitude': lon,
                            'phone': '—',
                            'working_hours': '',
                        },
                    )
                    if not created:
                        update_fields = ['address', 'updated_at']
                        store.address = store_address
                        if lat != Decimal('0') or lon != Decimal('0'):
                            store.latitude = lat
                            store.longitude = lon
                            update_fields.extend(['latitude', 'longitude'])
                        store.save(update_fields=update_fields)
                    product = form.save(commit=False)
                    product.store = store
                    product.photos = []
                    product.status = Product.Status.AVAILABLE
                    product.save()
                    paths = save_product_uploads(product, files)
                    product.photos = paths
                    product.save(update_fields=['photos'])
            except Exception:
                messages.error(
                    request,
                    'Не удалось сохранить товар или фото. Проверьте файлы (PNG, JPEG) и попробуйте снова.',
                )
                return render(
                    request,
                    'seller_add.html',
                    {'form': form, 'russian_cities': RUSSIAN_CITIES},
                )
            messages.success(request, 'Товар размещён.')
            return redirect(reverse('core:manager_cabinet'))
    else:
        form = ProductForm()

    return render(
        request,
        'seller_add.html',
        {'form': form, 'russian_cities': RUSSIAN_CITIES},
    )


@manager_required
@require_GET
def address_suggest(request):
    """JSON-подсказки адреса (Nominatim). Только для авторизованных управляющих/админов."""
    q = (request.GET.get('q') or '').strip()
    city = (request.GET.get('city') or '').strip()
    results = address_suggestions(q, city=city, limit=7)
    return JsonResponse({'results': results})


@manager_required
@require_POST
def complete_reservation(request, id):  # noqa: A002
    manager = get_session_user(request)
    reservation = get_object_or_404(
        Reservation.objects.select_related('product', 'product__store'),
        pk=id,
    )

    if (
        reservation.product.store.manager_id != manager.pk
        and not _is_global_admin(manager)
    ):
        messages.error(request, 'Нет доступа к этой брони.')
        return redirect(reverse('core:manager_cabinet'))

    posted_code = (request.POST.get('code') or '').strip()
    if posted_code != reservation.code:
        messages.error(request, 'Неверный код брони.')
        return redirect(reverse('core:manager_cabinet'))

    if reservation.status != Reservation.Status.ACTIVE:
        messages.warning(request, 'Бронь уже не активна.')
        return redirect(reverse('core:manager_cabinet'))

    with transaction.atomic():
        r = Reservation.objects.select_for_update().get(pk=reservation.pk)
        if r.status != Reservation.Status.ACTIVE:
            messages.warning(request, 'Бронь уже обработана.')
            return redirect(reverse('core:manager_cabinet'))
        if posted_code != r.code:
            messages.error(request, 'Неверный код брони.')
            return redirect(reverse('core:manager_cabinet'))
        p = Product.objects.select_for_update().get(pk=r.product_id)
        r.status = Reservation.Status.COMPLETED
        r.save(update_fields=['status', 'updated_at'])
        p.status = Product.Status.SOLD
        p.save(update_fields=['status', 'updated_at'])

    messages.success(request, 'Бронь завершена, товар отмечен как проданный.')
    return redirect(reverse('core:manager_cabinet'))

#тест

def api_debug(request):
    """Временный endpoint для отладки — отдаёт данные в JSON"""
    products = list(Product.objects.all().values(
        'id', 'title', 'price_original', 'price_discounted', 'status'
    ))
    reservations = list(Reservation.objects.all().values(
        'id', 'code', 'status', 'expires_at'
    ))

    return JsonResponse({
        'products_count': len(products),
        'products': products,
        'reservations_count': len(reservations),
        'reservations': reservations
    })
