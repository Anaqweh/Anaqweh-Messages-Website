import time
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_single_email_task(self, log_id: int):
    """Send one email for a given EmailLog entry."""
    from apps.campaigns.models import EmailLog
    from apps.campaigns.emailjs_service import send_via_emailjs

    try:
        log = EmailLog.objects.select_related('campaign', 'recipient').get(pk=log_id)
    except EmailLog.DoesNotExist:
        logger.error(f'EmailLog {log_id} not found')
        return

    if log.status == 'sent':
        return  # Already sent, skip

    log.status = 'sending'
    log.attempts += 1
    log.last_attempt_at = timezone.now()
    log.save(update_fields=['status', 'attempts', 'last_attempt_at'])

    # Build context for template variables
    context = {
        'name':           log.recipient_name or log.recipient_email,
        'email':          log.recipient_email,
        'phone':          log.recipient.phone if log.recipient else '',
        'course_name':    log.recipient.custom_field_1 if log.recipient else '',
        'custom_message': log.recipient.custom_field_2 if log.recipient else '',
    }

    # Render subject/body with variables
    subject  = log.campaign.subject
    body_html = log.campaign.body_html
    body_text = log.campaign.body_text

    for key, value in context.items():
        placeholder = '{{' + key + '}}'
        subject   = subject.replace(placeholder, str(value or ''))
        body_html = body_html.replace(placeholder, str(value or ''))
        body_text = body_text.replace(placeholder, str(value or ''))

    result = send_via_emailjs(
        to_email=log.recipient_email,
        to_name=log.recipient_name,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        extra_params=context,
    )

    if result['success']:
        log.status     = 'sent'
        log.sent_at    = timezone.now()
        log.message_id = result.get('message_id', '')
        log.emailjs_response = result.get('raw_response', {})
        log.error_message = ''
    else:
        error = result.get('error', 'خطأ غير معروف')
        retry_delay = settings.RETRY_DELAY_SECONDS

        if log.attempts < settings.MAX_RETRIES:
            log.status = 'pending'
            log.error_message = error
            log.save(update_fields=['status', 'attempts', 'last_attempt_at', 'error_message'])
            raise self.retry(exc=Exception(error), countdown=retry_delay)
        else:
            log.status = 'failed'
            log.error_message = error
            log.emailjs_response = result.get('raw_response', {})

    log.save(update_fields=['status', 'sent_at', 'message_id',
                            'emailjs_response', 'error_message', 'attempts'])


@shared_task(bind=True)
def run_campaign_task(self, campaign_id: int):
    """Dispatch all email tasks for a campaign in batches."""
    from apps.campaigns.models import Campaign, EmailLog
    from apps.recipients.models import Recipient, UnsubscribeList

    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        logger.error(f'Campaign {campaign_id} not found')
        return

    if campaign.status not in ('running', 'scheduled'):
        logger.info(f'Campaign {campaign_id} is {campaign.status}, skipping.')
        return

    campaign.status     = 'running'
    campaign.started_at = timezone.now()
    campaign.celery_task_id = self.request.id
    campaign.save(update_fields=['status', 'started_at', 'celery_task_id'])

    # Get global unsubscribed emails
    unsubscribed_global = set(
        UnsubscribeList.objects.values_list('email', flat=True)
    )

    # Get eligible recipients
    recipients = Recipient.objects.filter(
        mailing_list=campaign.mailing_list,
        is_active=True,
        is_unsubscribed=False,
    ).exclude(email__in=unsubscribed_global)

    batch_size  = settings.BATCH_SIZE
    batch_delay = settings.BATCH_DELAY_SECONDS
    total       = 0

    for i, recipient in enumerate(recipients.iterator(chunk_size=100)):
        # Skip if log already exists (resume support)
        log, created = EmailLog.objects.get_or_create(
            campaign=campaign,
            recipient=recipient,
            defaults={
                'recipient_name':  recipient.name,
                'recipient_email': recipient.email,
                'status':          'pending',
            }
        )
        if not created and log.status == 'sent':
            continue

        # Dispatch individual task
        send_single_email_task.apply_async(
            args=[log.id],
            countdown=0,
        )
        total += 1

        # Batch delay
        if total % batch_size == 0:
            time.sleep(batch_delay)

        # Check if campaign was paused/cancelled
        campaign.refresh_from_db()
        if campaign.status in ('paused', 'cancelled'):
            logger.info(f'Campaign {campaign_id} was {campaign.status}, stopping dispatch.')
            return

    logger.info(f'Campaign {campaign_id}: dispatched {total} tasks.')

    # Check if already completed
    campaign.refresh_from_db()
    if campaign.status == 'running':
        check_campaign_completion.apply_async(args=[campaign_id], countdown=30)


@shared_task
def check_campaign_completion(campaign_id: int):
    """Mark campaign as completed when all emails are processed."""
    from apps.campaigns.models import Campaign

    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return

    if campaign.status != 'running':
        return

    pending = campaign.logs.filter(status__in=['pending', 'sending']).count()
    if pending == 0:
        campaign.status       = 'completed'
        campaign.completed_at = timezone.now()
        campaign.save(update_fields=['status', 'completed_at'])
        logger.info(f'Campaign {campaign_id} completed.')
    else:
        # Re-check later
        check_campaign_completion.apply_async(args=[campaign_id], countdown=60)


@shared_task
def send_test_email_task(to_email: str, subject: str, body_html: str,
                         body_text: str = '', to_name: str = 'Test'):
    """Send a test email immediately."""
    from apps.campaigns.emailjs_service import send_via_emailjs
    return send_via_emailjs(
        to_email=to_email,
        to_name=to_name,
        subject=f'[اختبار] {subject}',
        body_html=body_html,
        body_text=body_text,
    )
