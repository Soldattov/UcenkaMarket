# core/services/bitrix24.py
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def send_reservation_to_bitrix24(reservation):
    """
    Отправляет данные о брони в Bitrix24 CRM через REST API.
    
    Args:
        reservation: Объект модели Reservation
        
    Returns:
        bool: True если успешно, False если ошибка
    """
    webhook = getattr(settings, 'BITRIX24_WEBHOOK', '').strip()
    
    if not webhook:
        logger.error('BITRIX24_WEBHOOK not configured')
        return False
    
    # === Маппинг полей: Django → Bitrix24 ===
    # Замени UF_CRM_* на реальные коды из твоей CRM!
    payload = {
        'fields': {
            'TITLE': f"Бронь #{reservation.code} — {reservation.product.title}",
            'UF_CRM_CODE': reservation.code,              # Код брони (строка)
            'UF_CRM_PRODUCT': reservation.product.title,  # Товар (строка)
            'UF_CRM_PRICE': str(reservation.product.price_discounted),  # Цена (число как строка)
            'UF_CRM_STATUS': reservation.get_status_display(),  # Статус (список)
            'UF_CRM_VISIT_TIME': reservation.visit_time.isoformat() if reservation.visit_time else '',
            'UF_CRM_PHONE': reservation.contact_phone or '',
            'UF_CRM_EMAIL': reservation.contact_email or '',
            'UF_CRM_EXPIRES_AT': reservation.expires_at.isoformat(),
            # Стандартные поля контакта
            'CONTACT_PHONE': reservation.contact_phone or '',
            'CONTACT_EMAIL': reservation.contact_email or '',
        },
        'params': {
            'REGISTER_SONET_EVENT': 'Y'  # Создать событие в ленте новостей
        }
    }
    
    # Метод API для создания сделки
    url = f"{webhook}crm.deal.add.json"
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get('result'):
            logger.info(f"✓ Deal created in Bitrix24: {result['result']}")
            return True
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"✗ Bitrix24 API error: {error}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("✗ Request timeout")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("✗ Connection error")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        return False