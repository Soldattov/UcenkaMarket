import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def validate_product_image_files(file_list):
    """Возвращает текст ошибки или None. Ожидается ровно три файла: основное и два дополнительных."""
    if not file_list or len(file_list) != 3:
        return 'Загрузите три фото: одно основное (на карточке в каталоге) и два дополнительных (только на странице товара). Форматы: PNG или JPEG.'
    for f in file_list:
        if f is None:
            return 'Заполните все три поля загрузки фото.'
        ext = Path(f.name).suffix.lower()
        if ext == '.jpg':
            ext = '.jpeg'
        if ext not in {'.png', '.jpeg'}:
            return f'Файл «{f.name}» не подходит. Разрешены только PNG и JPEG.'
    return None


def save_product_uploads(product, file_list):
    """
    Сохраняет файлы в MEDIA_ROOT, возвращает список относительных путей для Product.photos.
    """
    paths = []
    for f in file_list:
        ext = Path(f.name).suffix.lower()
        if ext == '.jpg':
            ext = '.jpeg'
        key = f'products/{product.pk}/{uuid.uuid4().hex}{ext}'
        default_storage.save(key, ContentFile(f.read()))
        paths.append(key)
    return paths
