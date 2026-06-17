import requests
import logging
from django.conf import settings
logger = logging.getLogger(__name__)
EMAILJS_API_URL = 'https://api.emailjs.com/api/v1.0/email/send'

def send_via_emailjs(to_email, to_name, subject, body_html, body_text='', extra_params=None, service_id=None, template_id=None):
    service_id = service_id or settings.EMAILJS_SERVICE_ID
    template_id = template_id or settings.EMAILJS_TEMPLATE_ID
    private_key = settings.EMAILJS_PRIVATE_KEY
    public_key = settings.EMAILJS_PUBLIC_KEY
    if not all([service_id, template_id, private_key, public_key]):
        return {'success': False, 'error': 'إعدادات EmailJS غير مكتملة', 'message_id': '', 'raw_response': {}}
    template_params = {'to_email': to_email, 'to_name': to_name or to_email, 'subject': subject, 'body_html': body_html, 'body_text': body_text}
    if extra_params:
        template_params.update(extra_params)
    payload = {'service_id': service_id, 'template_id': template_id, 'user_id': public_key, 'accessToken': private_key, 'template_params': template_params}
    try:
        resp = requests.post(EMAILJS_API_URL, json=payload, timeout=30, headers={'Content-Type': 'application/json'})
        if resp.status_code == 200:
            return {'success': True, 'message_id': resp.headers.get('X-Message-Id',''), 'raw_response': {'status': resp.status_code, 'text': resp.text}, 'error': ''}
        else:
            return {'success': False, 'error': f'EmailJS error {resp.status_code}: {resp.text}', 'message_id': '', 'raw_response': {'status': resp.status_code, 'text': resp.text}}
    except Exception as e:
        return {'success': False, 'error': str(e), 'message_id': '', 'raw_response': {}}
