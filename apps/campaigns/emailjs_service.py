import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)
EMAILJS_API_URL = 'https://api.emailjs.com/api/v1.0/email/send'


def get_user_emailjs_config(user):
    if user and not user.is_anonymous:
        try:
            cfg = user.emailjs_config
            if cfg.is_configured and all([cfg.service_id, cfg.template_id, cfg.public_key, cfg.private_key]):
                return {
                    'service_id':  cfg.service_id,
                    'template_id': cfg.template_id,
                    'public_key':  cfg.public_key,
                    'private_key': cfg.private_key,
                    'from_email':  cfg.from_email,
                    'from_name':   cfg.from_name,
                }
        except Exception:
            pass
    return {
        'service_id':  settings.EMAILJS_SERVICE_ID,
        'template_id': settings.EMAILJS_TEMPLATE_ID,
        'public_key':  settings.EMAILJS_PUBLIC_KEY,
        'private_key': settings.EMAILJS_PRIVATE_KEY,
        'from_email':  '',
        'from_name':   '',
    }


def send_via_emailjs(to_email, to_name, subject, body_html,
                     body_text='', extra_params=None,
                     service_id=None, template_id=None, user=None):
    body_html = ensure_email_payment_links(body_html)

    if user and not (service_id and template_id):
        cfg = get_user_emailjs_config(user)
        service_id  = service_id  or cfg['service_id']
        template_id = template_id or cfg['template_id']
        private_key = cfg['private_key']
        public_key  = cfg['public_key']
    else:
        private_key = settings.EMAILJS_PRIVATE_KEY
        public_key  = settings.EMAILJS_PUBLIC_KEY

    if not all([service_id, template_id, private_key, public_key]):
        return {'success': False, 'error': 'إعدادات EmailJS غير مكتملة', 'message_id': '', 'raw_response': {}}

    template_params = {
        'to_email':  to_email,
        'to_name':   to_name or to_email,
        'subject':   subject,
        'message':   body_html,
        'body_html': body_html,
        'body_text': body_text,
    }
    if extra_params:
        template_params.update(extra_params)

    payload = {
        'service_id':      service_id,
        'template_id':     template_id,
        'user_id':         public_key,
        'accessToken':     private_key,
        'template_params': template_params,
    }
    try:
        resp = requests.post(EMAILJS_API_URL, json=payload, timeout=30,
                             headers={'Content-Type': 'application/json'})
        if resp.status_code == 200:
            return {'success': True, 'message_id': resp.headers.get('X-Message-Id', ''),
                    'raw_response': {'status': resp.status_code, 'text': resp.text}, 'error': ''}
        else:
            return {'success': False, 'error': f'EmailJS error {resp.status_code}: {resp.text}',
                    'message_id': '', 'raw_response': {'status': resp.status_code, 'text': resp.text}}
    except Exception as e:
        return {'success': False, 'error': str(e), 'message_id': '', 'raw_response': {}}


def ensure_email_payment_links(body_html):
    import re
    from urllib.parse import urlencode

    if not body_html:
        return body_html

    base_url = 'http://165.232.167.39:8000'

    def plain(html):
        s = re.sub(r'<[^>]+>', '', html or '')
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def detect_amount(src):
        m = re.search(r'(?:data-amount|amount)=["\']?([0-9]+(?:\.[0-9]+)?)', src or '', re.I)
        return m.group(1) if m else '2'

    def make_url(src, label):
        return base_url + '/templates/pay/quick/?' + urlencode({
            'amount': detect_amount(src),
            'label': label or 'ادفع الآن',
        })

    def is_payment(inner, attrs=''):
        t = (plain(inner) + ' ' + (attrs or '')).lower()
        return ('ادفع' in t) or ('دفع' in t) or ('pay' in t) or ('payment' in t)

    def fix_a(m):
        attrs1 = m.group(1) or ''
        href = (m.group(2) or '').strip()
        attrs2 = m.group(3) or ''
        inner = m.group(4) or ''
        attrs = attrs1 + ' ' + attrs2

        if not is_payment(inner, attrs):
            return m.group(0)

        if href and href not in ['#', '/', 'javascript:void(0)', 'javascript:;']:
            return m.group(0)

        label = plain(inner) or 'ادفع الآن'
        url = make_url(m.group(0), label)
        final_attrs = attrs1 + ' href="' + url + '" ' + attrs2
        if 'target=' not in final_attrs.lower():
            final_attrs += ' target="_blank"'
        return '<a' + final_attrs + '>' + inner + '</a>'

    body_html = re.sub(
        r'<a\b([^>]*)href=["\']([^"\']*)["\']([^>]*)>(.*?)</a>',
        fix_a,
        body_html,
        flags=re.I | re.S
    )

    def fix_button(m):
        attrs = m.group(1) or ''
        inner = m.group(2) or ''
        if not is_payment(inner, attrs):
            return m.group(0)
        label = plain(inner) or 'ادفع الآن'
        url = make_url(m.group(0), label)
        return '<a href="' + url + '" target="_blank" style="display:inline-block;background:#10b981;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:bold">' + label + '</a>'

    body_html = re.sub(r'<button\b([^>]*)>(.*?)</button>', fix_button, body_html, flags=re.I | re.S)
    return body_html


# === FINAL FIX: EmailJS server sender override ===
def send_via_emailjs(to_email, to_name, subject, body_html, body_text='', extra_params=None, service_id=None, template_id=None, user=None):
    import requests
    from django.conf import settings

    try:
        from decouple import config
    except Exception:
        config = None

    def cfg(name, default=''):
        value = getattr(settings, name, '') or ''
        if not value and config:
            value = config(name, default=default) or ''
        return value

    sid = service_id or cfg('EMAILJS_SERVICE_ID') or cfg('EMAILJS_SERVICE')
    tid = template_id or cfg('EMAILJS_TEMPLATE_ID') or cfg('EMAILJS_TEMPLATE')
    public_key = cfg('EMAILJS_PUBLIC_KEY') or cfg('EMAILJS_USER_ID')
    private_key = cfg('EMAILJS_PRIVATE_KEY') or cfg('EMAILJS_ACCESS_TOKEN')

    missing = []
    if not sid:
        missing.append('EMAILJS_SERVICE_ID')
    if not tid:
        missing.append('EMAILJS_TEMPLATE_ID')
    if not public_key:
        missing.append('EMAILJS_PUBLIC_KEY')

    if missing:
        return {
            'success': False,
            'error': 'إعدادات EmailJS غير مكتملة: ' + ', '.join(missing),
            'message_id': '',
            'raw_response': {},
        }

    params = {
        'to_email': to_email,
        'to_name': to_name or to_email,
        'subject': subject,
        'message': body_html,
        'body_html': body_html,
        'html': body_html,
        'body_text': body_text or '',
        'reply_to': to_email,
    }

    if extra_params:
        params.update(extra_params)

    payload = {
        'service_id': sid,
        'template_id': tid,
        'user_id': public_key,
        'template_params': params,
    }

    if private_key:
        payload['accessToken'] = private_key

    try:
        response = requests.post(
            'https://api.emailjs.com/api/v1.0/email/send',
            json=payload,
            timeout=25,
        )
        ok = 200 <= response.status_code < 300
        return {
            'success': ok,
            'error': '' if ok else response.text[:800],
            'message_id': response.headers.get('x-message-id', ''),
            'raw_response': {
                'status_code': response.status_code,
                'text': response.text[:1000],
            },
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message_id': '',
            'raw_response': {},
        }


# === FINAL OVERRIDE: read EmailJS values directly from .env and ignore placeholders ===
def send_via_emailjs(to_email, to_name, subject, body_html, body_text='', extra_params=None, service_id=None, template_id=None, user=None):
    import requests
    from pathlib import Path

    def env_value(name):
        try:
            for line in Path('.env').read_text(errors='ignore').replace('\r','').splitlines():
                if line.startswith(name + '='):
                    value = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if value and not value.startswith('your_'):
                        return value
        except Exception:
            pass
        return ''

    sid = service_id or env_value('EMAILJS_SERVICE_ID')
    tid = template_id or env_value('EMAILJS_TEMPLATE_ID')
    public_key = env_value('EMAILJS_PUBLIC_KEY') or env_value('EMAILJS_USER_ID')
    private_key = env_value('EMAILJS_PRIVATE_KEY')

    if not sid or not tid or not public_key:
        return {
            'success': False,
            'error': f'EmailJS missing values service={bool(sid)} template={bool(tid)} public={bool(public_key)}',
            'message_id': '',
            'raw_response': {},
        }

    params = {
        'to_email': to_email,
        'to_name': to_name or to_email,
        'subject': subject,
        'message': body_html,
        'body_html': body_html,
        'html': body_html,
        'body_text': body_text or '',
        'reply_to': 'info@inexc.com',
        'from_name': 'INEXC - شركة التميز الابتكاري',
        'from_email': 'info@inexc.com',
    }
    if extra_params:
        params.update(extra_params)

    payload = {
        'service_id': sid,
        'template_id': tid,
        'user_id': public_key,
        'template_params': params,
    }
    if private_key and not private_key.startswith('your_'):
        payload['accessToken'] = private_key

    try:
        r = requests.post('https://api.emailjs.com/api/v1.0/email/send', json=payload, timeout=25)
        ok = 200 <= r.status_code < 300
        return {
            'success': ok,
            'error': '' if ok else r.text[:800],
            'message_id': r.headers.get('x-message-id', ''),
            'raw_response': {'status_code': r.status_code, 'text': r.text[:1000]},
        }
    except Exception as e:
        return {'success': False, 'error': str(e), 'message_id': '', 'raw_response': {}}

