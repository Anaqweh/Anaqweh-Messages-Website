from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Send due message steps for campaigns.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from django.conf import settings
        from apps.campaigns.models import CampaignMessageStep, EmailLog
        from apps.campaigns.tasks import send_single_email_task
        from apps.recipients.models import Recipient, UnsubscribeList

        now = timezone.now()
        steps = CampaignMessageStep.objects.select_related('campaign').filter(
            is_active=True,
            sent_at__isnull=True,
            send_at__isnull=False,
            send_at__lte=now,
        )

        if options['dry_run']:
            self.stdout.write(f'Due message steps: {steps.count()}')
            for step in steps[:50]:
                self.stdout.write(f'- #{step.id} campaign={step.campaign_id} step={step.step_number} send_at={step.send_at} subject={step.subject}')
            return

        old_always_eager = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        old_eager_propagates = getattr(settings, 'CELERY_TASK_EAGER_PROPAGATES', False)
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = False

        attempted = 0
        processed = 0
        try:
            for step in steps:
                campaign = step.campaign
                unsubscribed = set(UnsubscribeList.objects.values_list('email', flat=True))
                recipients = Recipient.objects.filter(
                    mailing_list=campaign.mailing_list,
                    is_active=True,
                    is_unsubscribed=False,
                ).exclude(email__in=unsubscribed)

                for recipient in recipients.iterator(chunk_size=100):
                    log, created = EmailLog.objects.get_or_create(
                        campaign=campaign,
                        message_step=step,
                        recipient=recipient,
                        defaults={
                            'recipient_name': recipient.name,
                            'recipient_email': recipient.email,
                            'status': 'pending',
                            'subject_snapshot': step.subject,
                            'body_html_snapshot': step.body_html,
                            'body_text_snapshot': step.body_text,
                        },
                    )
                    if not created and log.status == 'sent':
                        continue
                    log.subject_snapshot = step.subject
                    log.body_html_snapshot = step.body_html
                    log.body_text_snapshot = step.body_text
                    log.save(update_fields=['subject_snapshot', 'body_html_snapshot', 'body_text_snapshot'])
                    send_single_email_task.apply(args=[log.id])
                    attempted += 1

                step.sent_at = timezone.now()
                step.save(update_fields=['sent_at'])
                processed += 1
        finally:
            settings.CELERY_TASK_ALWAYS_EAGER = old_always_eager
            settings.CELERY_TASK_EAGER_PROPAGATES = old_eager_propagates

        self.stdout.write(self.style.SUCCESS(f'Processed {processed} message steps, attempted {attempted} emails'))
