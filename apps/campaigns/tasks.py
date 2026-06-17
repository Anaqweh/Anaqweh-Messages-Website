import time
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_single_email_task(self, log_id):
    from apps.campaigns.models import EmailLog
    from apps.campaigns.emailjs_service import send_via_emailjs
    from apps.campaigns.tracking import inject_tracking
    from decouple import config as _cfg
    try:
        log = EmailLog.objects.select_related('campaign','recipient').get(pk=log_id)
    except EmailLog.DoesNotExist:
        return
    if log.status == 'sent':
        return
    log.status = 'sending'
    log.attempts += 1
    log.last_attempt_at = timezone.now()
    log.save(update_fields=['status','attempts','last_attempt_at'])
    context = {'name': log.recipient_name or log.recipient_email, 'email': log.recipient_email, 'phone': log.recipient.phone if log.recipient else '', 'course_name': log.recipient.custom_field_1 if log.recipient else '', 'custom_message': log.recipient.custom_field_2 if log.recipient else ''}
    if log.campaign.ab_test_enabled and log.recipient and (log.recipient.id % 2 == 1):
        subject = log.campaign.subject_b or log.campaign.subject
        body_html = log.campaign.body_html_b or log.campaign.body_html
        body_text = log.campaign.body_text
        log.message_id = (log.message_id or '') + '[B]'
    else:
        subject = log.campaign.subject
        body_html = log.campaign.body_html
        body_text = log.campaign.body_text
    for key, value in context.items():
        p = '{{' + key + '}}'
        subject = subject.replace(p, str(value or ''))
        body_html = body_html.replace(p, str(value or ''))
        body_text = body_text.replace(p, str(value or ''))
    base_url = _cfg('SITE_URL', default='http://165.232.167.39:8000')
    body_html = inject_tracking(body_html, log.id, base_url)
    result = send_via_emailjs(to_email=log.recipient_email, to_name=log.recipient_name, subject=subject, body_html=body_html, body_text=body_text, extra_params=context)
    if result['success']:
        log.status = 'sent'
        log.sent_at = timezone.now()
        log.message_id = result.get('message_id','')
        log.emailjs_response = result.get('raw_response',{})
        log.error_message = ''
    else:
        error = result.get('error','خطأ غير معروف')
        if log.attempts < settings.MAX_RETRIES:
            log.status = 'pending'
            log.error_message = error
            log.save(update_fields=['status','attempts','last_attempt_at','error_message'])
            raise self.retry(exc=Exception(error), countdown=settings.RETRY_DELAY_SECONDS)
        else:
            log.status = 'failed'
            log.error_message = error
            log.emailjs_response = result.get('raw_response',{})
    log.save(update_fields=['status','sent_at','message_id','emailjs_response','error_message','attempts'])

@shared_task(bind=True)
def run_campaign_task(self, campaign_id):
    from apps.campaigns.models import Campaign, EmailLog
    from apps.recipients.models import Recipient, UnsubscribeList
    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return
    if campaign.status not in ('running','scheduled'):
        return
    campaign.status = 'running'
    campaign.started_at = timezone.now()
    campaign.celery_task_id = self.request.id
    campaign.save(update_fields=['status','started_at','celery_task_id'])
    unsubscribed = set(UnsubscribeList.objects.values_list('email', flat=True))
    recipients = Recipient.objects.filter(mailing_list=campaign.mailing_list, is_active=True, is_unsubscribed=False).exclude(email__in=unsubscribed)
    total = 0
    for i, recipient in enumerate(recipients.iterator(chunk_size=100)):
        log, created = EmailLog.objects.get_or_create(campaign=campaign, recipient=recipient, defaults={'recipient_name': recipient.name, 'recipient_email': recipient.email, 'status': 'pending'})
        if not created and log.status == 'sent':
            continue
        send_single_email_task.apply_async(args=[log.id], countdown=0)
        total += 1
        if total % settings.BATCH_SIZE == 0:
            time.sleep(settings.BATCH_DELAY_SECONDS)
        campaign.refresh_from_db()
        if campaign.status in ('paused','cancelled'):
            return
    if campaign.status == 'running':
        check_campaign_completion.apply_async(args=[campaign_id], countdown=30)

@shared_task
def check_campaign_completion(campaign_id):
    from apps.campaigns.models import Campaign
    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return
    if campaign.status != 'running':
        return
    if campaign.logs.filter(status__in=['pending','sending']).count() == 0:
        campaign.status = 'completed'
        campaign.completed_at = timezone.now()
        campaign.save(update_fields=['status','completed_at'])
        send_completion_notification.delay(campaign_id)
    else:
        check_campaign_completion.apply_async(args=[campaign_id], countdown=60)

@shared_task
def send_test_email_task(to_email, subject, body_html, body_text='', to_name='Test'):
    from apps.campaigns.emailjs_service import send_via_emailjs
    return send_via_emailjs(to_email=to_email, to_name=to_name, subject=f'[اختبار] {subject}', body_html=body_html, body_text=body_text)


@shared_task
def process_recurring_campaigns():
    """Runs periodically: re-launch campaigns whose next_run is due."""
    from apps.campaigns.models import Campaign
    from django.utils import timezone
    from datetime import timedelta
    now = timezone.now()
    due = Campaign.objects.filter(is_recurring_active=True, next_run__lte=now)
    for c in due:
        # Clone-run: reset logs and relaunch
        run_campaign_task.delay(c.id)
        # Schedule next run
        if c.recurrence == 'daily':
            c.next_run = now + timedelta(days=1)
        elif c.recurrence == 'weekly':
            c.next_run = now + timedelta(weeks=1)
        elif c.recurrence == 'monthly':
            c.next_run = now + timedelta(days=30)
        c.save(update_fields=['next_run'])
    return f'Processed {due.count()} recurring campaigns'


@shared_task
def send_completion_notification(campaign_id):
    """Notify admin when a campaign completes."""
    from apps.campaigns.models import Campaign
    from apps.campaigns.emailjs_service import send_via_emailjs
    from decouple import config
    try:
        c = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return
    admin_email = config('ADMIN_EMAIL', default='admin@inexc.com')
    html = f"""
    <div style='font-family:Arial;direction:rtl;padding:20px'>
      <h2 style='color:#1e3a6e'>اكتملت الحملة: {c.name}</h2>
      <p>إجمالي المستلمين: <b>{c.total_recipients}</b></p>
      <p>تم الإرسال بنجاح: <b style='color:green'>{c.sent_count}</b></p>
      <p>فشل: <b style='color:red'>{c.failed_count}</b></p>
      <p>معدل النجاح: <b>{c.success_rate}%</b></p>
    </div>
    """
    send_via_emailjs(to_email=admin_email, to_name='المشرف',
                     subject=f'اكتملت الحملة: {c.name}', body_html=html)
    return 'notification sent'
