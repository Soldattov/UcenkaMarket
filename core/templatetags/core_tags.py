from django import template
from django.conf import settings

register = template.Library()


@register.filter
def product_media_url(path):
    """Путь из JSON (относительный) или внешний URL для тега img."""
    if not path:
        return ''
    s = str(path)
    if s.startswith(('http://', 'https://')):
        return s
    base = settings.MEDIA_URL.rstrip('/')
    return f'{base}/{s.lstrip("/")}'
