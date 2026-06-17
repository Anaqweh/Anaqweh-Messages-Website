"""
EmailJS REST API integration.
Docs: https://www.emailjs.com/docs/rest-api/send/
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

EMAILJS_API_URL = 'https://api.emailjs.com/api/v1.0/email/send'


def send_via_emailjs(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    body_text: str = '',
    extra_params: dict = None,
    service_id: str = None,
    template_id: str = None,
) -> dict:
    """
    Send a single email through EmailJS REST API.

    Returns:
        dict with keys: success (bool), message_id (str), raw_response (dict), error (str)
    """
    service_id  = service_id  or settings.EMAILJS_SERVICE_ID
    template_id = template_id or settings.EMAILJS_TEMPLATE_ID
    private_key = settings.EMAILJS_PRIVATE_KEY
    public_key  = settings.EMAILJS_PUBLIC_KEY

    if not all([service_id, template_id, private_key, public_key]):
        return {
            'success': False,
            'error': 'إعدادات EmailJS غير مكتملة. تحقق من ملف .env',
            'message_id': '',
            'raw_response': {},
        }

    # Template params – these map to your EmailJS template variables
    template_params = {
        'to_email':   to_email,
        'to_name':    to_name or to_email,
        'subject':    subject,
        'body_html':  body_html,
        'body_text':  body_text or '',
        'reply_to':   settings.ADMIN_EMAIL if hasattr(settings, 'ADMIN_EMAIL') else '',
    }
    if extra_params:
        template_params.update(extra_params)

    payload = {
        'service_id':       service_id,
        'template_id':      template_id,
        'user_id':          public_key,
        'accessToken':      private_key,
        'template_params':  template_params,
    }

    try:
        resp = requests.post(
            EMAILJS_API_URL,
            json=payload,
            timeout=30,
            headers={'Content-Type': 'application/json'},
        )

        if resp.status_code == 200:
            logger.info(f'[EmailJS] ✅ Sent to {to_email}')
            return {
                'success':     True,
                'message_id':  resp.headers.get('X-Message-Id', ''),
                'raw_response': {'status': resp.status_code, 'text': resp.text},
                'error':       '',
            }
        else:
            error_msg = f'EmailJS error {resp.status_code}: {resp.text}'
            logger.warning(f'[EmailJS] ❌ {to_email} – {error_msg}')
            return {
                'success':     False,
                'error':       error_msg,
                'message_id':  '',
                'raw_response': {'status': resp.status_code, 'text': resp.text},
            }

    except requests.exceptions.Timeout:
        err = 'انتهت مهلة الاتصال بـ EmailJS'
        logger.error(f'[EmailJS] Timeout for {to_email}')
        return {'success': False, 'error': err, 'message_id': '', 'raw_response': {}}

    except requests.exceptions.RequestException as e:
        err = f'خطأ في الاتصال: {str(e)}'
        logger.error(f'[EmailJS] RequestException for {to_email}: {e}')
        return {'success': False, 'error': err, 'message_id': '', 'raw_response': {}}
