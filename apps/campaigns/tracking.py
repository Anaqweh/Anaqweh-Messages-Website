import base64, re
from urllib.parse import quote, unquote
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone

TRACKING_PIXEL = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')

def inject_tracking(html, log_id, base_url):
    if not html:
        return html
    def wrap_link(match):
        url = match.group(1)
        if url.startswith('#') or url.startswith('mailto:') or 'unsubscribe' in url.lower():
            return match.group(0)
        return f'href="{base_url}/track/click/{log_id}/?url={quote(url, safe="")}"'
    html = re.sub(r'href="([^"]+)"', wrap_link, html)
    pixel = f'<img src="{base_url}/track/open/{log_id}/" width="1" height="1" style="display:none" alt="" />'
    if '</body>' in html:
        html = html.replace('</body>', pixel + '</body>')
    else:
        html += pixel
    return html

def track_open(request, log_id):
    from apps.campaigns.models import EmailLog
    try:
        log = EmailLog.objects.get(pk=log_id)
        if log.status == 'sent':
            log.status = 'opened'
            log.opened_at = timezone.now()
            log.save(update_fields=['status', 'opened_at'])
        EmailLog.objects.filter(pk=log_id).update(open_count=(log.open_count or 0) + 1)
    except EmailLog.DoesNotExist:
        pass
    response = HttpResponse(TRACKING_PIXEL, content_type='image/gif')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

def track_click(request, log_id):
    from apps.campaigns.models import EmailLog
    url = unquote(request.GET.get('url', '/'))
    try:
        log = EmailLog.objects.get(pk=log_id)
        log.status = 'clicked'
        log.clicked_at = timezone.now()
        log.click_count = (log.click_count or 0) + 1
        log.save(update_fields=['status', 'clicked_at', 'click_count'])
    except EmailLog.DoesNotExist:
        pass
    return HttpResponseRedirect(url)
