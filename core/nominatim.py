"""Подсказки адреса через Nominatim (OSM). См. https://operations.osmfoundation.org/policies/nominatim/"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
# Укажите реальный контакт при публикации в продакшене.
USER_AGENT = 'UcenkaMarket/1.0 (Django; internal geocoding suggestions)'


def address_suggestions(query: str, city: str = '', limit: int = 6) -> list[dict]:
    """
    Возвращает список словарей: display_name, lat, lon.
    При ошибке сети или пустом запросе — пустой список.
    """
    q = (query or '').strip()
    if len(q) < 3:
        return []

    parts = [q]
    if (city or '').strip():
        parts.append(city.strip())
    parts.append('Россия')
    search_q = ', '.join(parts)

    params = urllib.parse.urlencode(
        {
            'q': search_q,
            'format': 'json',
            'limit': str(limit),
            'accept-language': 'ru',
            'countrycodes': 'ru',
        }
    )
    url = f'{NOMINATIM_URL}?{params}'
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode('utf-8')
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.warning('Nominatim request failed: %s', e)
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    out = []
    for row in data:
        lat, lon = row.get('lat'), row.get('lon')
        name = row.get('display_name') or ''
        if not lat or not lon or not name:
            continue
        out.append({'display_name': name, 'lat': lat, 'lon': lon})
    return out
