
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def send_reservation_to_bitrix24(reservation):
    worker_url = getattr(settings, 'CLOUDFLARE_WORKER_URL', '').strip()
    if not worker_url:
        logger.error('CLOUDFLARE_WORKER_URL not configured')
        return False

    payload = {
        'code': reservation.code,
        'product': reservation.product.title,
        'price': str(reservation.product.price_discounted),
        'status': reservation.get_status_display(),
        'phone': reservation.contact_phone or '',
        'email': reservation.contact_email or '',
        'visit_time': reservation.visit_time.isoformat() if reservation.visit_time else '',
        'expires_at': reservation.expires_at.isoformat(),
    }

    try:
        response = requests.post(worker_url, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()

        # Логируем ответ для отладки
        logger.info(f"Worker response: {result.get('bitrix_result', {})}")

        bitrix_result = result.get('bitrix_result', {})
        if bitrix_result.get('result'):
            logger.info(f"✓ Deal created: {bitrix_result['result']}")
            return True
        elif bitrix_result.get('error'):
            logger.error(f"✗ Bitrix24 error: {bitrix_result.get('error_description', bitrix_result['error'])}")
            return False
        else:
            logger.warning(f"⚠ Unexpected response: {result}")
            return False

    except Exception as e:
        logger.error(f"✗ Request failed: {e}")
        return False