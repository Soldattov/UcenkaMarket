# УценкаМаркет

Агрегатор уценённых товаров с нарушенной упаковкой или мелким браком

## О проекте

УценкаМаркет — это веб-платформа, которая соединяет розничные магазины с покупателями, ищущими выгоду. Магазины размещают товары с нарушенной упаковкой, витринные образцы и изделия с мелким браком со скидкой до 70%. Покупатели находят уценку рядом, изучают фото дефекта и бронируют товар на 24 часа.

## Какую проблему решает

Для магазинов:
- Возврат 30–90% стоимости вместо списания
- Освобождение складских площадей
- Быстрое размещение товаров

Для покупателей:
- Экономия до 70% на исправных товарах
- Прозрачное описание дефекта с фото
- Бронь на 24 часа — товар не продадут

## Технологический стек

Backend: Python 3.13,1, Django 4.2
Database: SQLite3
Frontend: Django Templates, Bootstrap 5, HTML/CSS/JS
Authentication: Django Auth (телефон + роль)
Version Control: Git, GitHub

## Структура проекта

ucenkamarket/
├── config/ — Настройки проекта Django
├── core/ — Основное приложение
│   ├── models.py — Модели данных
│   ├── views.py — Views для экранов
│   ├── urls.py — Маршруты
│   ├── forms.py — Формы
│   └── templates/ — HTML-шаблоны
├── manage.py
├── requirements.txt
└── README.md

## Модель данных

Основные сущности:

User — Пользователь (покупатель/управляющий)
Поля: phone, role, is_verified, created_at, updated_at

Product — Товар с уценкой
Поля: title, price_original, price_discounted, defect_type, store, address, city, category, photos, status

Store — Магазин
Поля: name, address, phone, working_hours, manager

Reservation — Бронь на 24 часа
Поля: product, user, code, status, expires_at, visit_time

Category — Категория товаров
Поля: name, slug, is_active

DefectType — Тип дефекта
Поля: name, description, is_active

## Быстрый старт

Требования:
- Python 3.12+
- PostgreSQL 15+ (для production)
- Git

Установка локально:

1. Клонировать репозиторий
git clone https://github.com/yourusername/ucenkamarket.git
cd ucenkamarket

2. Создать виртуальное окружение
python -m venv venv

3. Активировать (Windows)
.\venv\Scripts\Activate.ps1

4. Установить зависимости
pip install -r requirements.txt

5. Применить миграции
python manage.py migrate

6. Создать суперпользователя
python manage.py createsuperuser

7. Запустить сервер
python manage.py runserver

Откройте http://127.0.0.1:8000/ в браузере

## Экраны

1. Вход / Регистрация — /
2. Каталог уценки — /catalog/
3. Карточка товара — /product/<id>/
4. Оформление брони — /product/<id>/reserve/
5. ЛК покупателя — /buyer/cabinet/
6. ЛК управляющего — /manager/cabinet/
7. Размещение товара — /seller/add/

## Роли и права

Guest — неавторизованный пользователь (только просмотр страницы входа)
Buyer — покупатель (бронирование, просмотр своих броней)
Manager — управляющий магазином (размещение товаров, управление бронями)
Admin — администратор (полный доступ)

## Автор

Студент: Солдатов Р.В.
Группа: КИ23-12Б
Университет: СФУ, ИКИТ
Кафедра: Системы искусственного интеллекта

## Лицензия

Учебный проект. Все права защищены.