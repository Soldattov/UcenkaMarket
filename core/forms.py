from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, When

from .catalog_constants import CATEGORY_SLUGS, DEFECT_NAMES
from .models import Category, DefectType, Product, Reservation, User


def _ctrl(**extra):
    attrs = {'class': 'form-control'}
    attrs.update(extra)
    return attrs


class LoginForm(forms.Form):
    phone = forms.CharField(
        label='Телефон',
        max_length=150,
        widget=forms.TextInput(
            attrs=_ctrl(
                type='tel',
                inputmode='tel',
                autocomplete='tel',
                placeholder='+7 (999) 123-45-67',
                pattern=r'\+?[0-9\s\-\(\)]{10,25}',
                title='Номер телефона, например +7 (999) 123-45-67',
            ),
        ),
    )

    def clean_phone(self):
        return self.cleaned_data['phone'].strip()
    password = forms.CharField(
        label='Пароль',
        strip=False,
        widget=forms.PasswordInput(attrs=_ctrl(autocomplete='current-password')),
    )


class RegisterForm(forms.Form):
    first_name = forms.CharField(
        label='Имя',
        max_length=150,
        widget=forms.TextInput(attrs=_ctrl(placeholder='Как к вам обращаться')),
    )
    phone = forms.CharField(
        label='Телефон',
        max_length=150,
        widget=forms.TextInput(
            attrs=_ctrl(
                type='tel',
                inputmode='tel',
                autocomplete='tel',
                placeholder='+7 (999) 123-45-67',
                pattern=r'\+?[0-9\s\-\(\)]{10,25}',
                title='Номер телефона, например +7 (999) 123-45-67',
            ),
        ),
    )
    email = forms.EmailField(
        label='Электронная почта',
        widget=forms.EmailInput(
            attrs=_ctrl(
                autocomplete='email',
                placeholder='name@example.com',
                inputmode='email',
            ),
        ),
    )
    password = forms.CharField(
        label='Пароль',
        strip=False,
        widget=forms.PasswordInput(attrs=_ctrl(autocomplete='new-password')),
    )
    password_confirm = forms.CharField(
        label='Пароль ещё раз',
        strip=False,
        widget=forms.PasswordInput(attrs=_ctrl(autocomplete='new-password')),
    )
    role = forms.ChoiceField(
        label='Роль',
        choices=User.Role.choices,
        widget=forms.Select(attrs=_ctrl()),
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if User.objects.filter(username=phone).exists():
            raise ValidationError('Этот номер уже зарегистрирован. Войдите с паролём.')
        return phone

    def clean_password(self):
        password = self.cleaned_data['password']
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password_confirm')
        if p1 is not None and p2 is not None and p1 != p2:
            raise ValidationError({'password_confirm': 'Пароли не совпадают.'})
        return cleaned


class ProductForm(forms.ModelForm):
    store_name = forms.CharField(
        label='Магазин',
        max_length=255,
        widget=forms.TextInput(
            attrs=_ctrl(placeholder='Название точки или сети'),
        ),
    )
    store_city = forms.CharField(
        label='Город',
        max_length=128,
        widget=forms.TextInput(
            attrs=_ctrl(
                placeholder='Начните ввод или выберите из списка',
                autocomplete='address-level2',
                list='um-ru-cities',
            ),
        ),
    )
    store_address = forms.CharField(
        label='Адрес',
        max_length=500,
        widget=forms.TextInput(
            attrs={
                **_ctrl(
                    placeholder='Улица, дом — при вводе появятся подсказки (OpenStreetMap)',
                    autocomplete='street-address',
                ),
                'data-address-suggest': '1',
            },
        ),
    )

    field_order = [
        'title',
        'description',
        'store_name',
        'store_city',
        'store_address',
        'price_original',
        'price_discounted',
        'category',
        'defect_type',
    ]

    class Meta:
        model = Product
        fields = (
            'title',
            'description',
            'price_original',
            'price_discounted',
            'category',
            'defect_type',
        )
        widgets = {
            'title': forms.TextInput(attrs=_ctrl()),
            'description': forms.Textarea(attrs=_ctrl(rows=4)),
            'price_original': forms.NumberInput(attrs=_ctrl(step='0.01', min='0')),
            'price_discounted': forms.NumberInput(attrs=_ctrl(step='0.01', min='0')),
            'category': forms.Select(attrs=_ctrl()),
            'defect_type': forms.Select(attrs=_ctrl()),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cat_order = [
            When(slug=s, then=i) for i, s in enumerate(CATEGORY_SLUGS)
        ]
        self.fields['category'].queryset = (
            Category.objects.filter(slug__in=CATEGORY_SLUGS, is_active=True)
            .annotate(
                _sort=Case(
                    *cat_order,
                    default=99,
                    output_field=IntegerField(),
                ),
            )
            .order_by('_sort')
        )
        self.fields['category'].empty_label = None
        def_order = [
            When(name=n, then=i) for i, n in enumerate(DEFECT_NAMES)
        ]
        self.fields['defect_type'].queryset = (
            DefectType.objects.filter(name__in=DEFECT_NAMES, is_active=True)
            .annotate(
                _sort=Case(
                    *def_order,
                    default=99,
                    output_field=IntegerField(),
                ),
            )
            .order_by('_sort')
        )
        self.fields['defect_type'].empty_label = None

    def clean_store_name(self):
        name = self.cleaned_data['store_name'].strip()
        if not name:
            raise ValidationError('Укажите название магазина.')
        return name

    def clean_store_city(self):
        city = self.cleaned_data['store_city'].strip()
        if len(city) < 2:
            raise ValidationError('Укажите город (не короче 2 символов).')
        return city

    def clean_store_address(self):
        addr = self.cleaned_data['store_address'].strip()
        if len(addr) < 3:
            raise ValidationError('Укажите адрес (не короче 3 символов).')
        return addr

    def clean(self):
        cleaned = super().clean()
        original = cleaned.get('price_original')
        discounted = cleaned.get('price_discounted')
        if original is not None and discounted is not None and discounted >= original:
            raise ValidationError(
                {'price_discounted': 'Цена со скидкой должна быть меньше оригинальной.'}
            )
        return cleaned


class ReservationForm(forms.ModelForm):
    visit_time = forms.DateTimeField(
        label='Время визита',
        required=False,
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs=_ctrl(type='datetime-local'),
        ),
        input_formats=[
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%d.%m.%Y %H:%M',
        ],
    )

    class Meta:
        model = Reservation
        fields = ('user', 'visit_time')
        widgets = {
            'user': forms.Select(attrs=_ctrl()),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].label = 'Покупатель'
