from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Send recurring campaigns whose next_run is due, without requiring a Celery worker.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only list due recurring campaigns; do not send anything.',
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from apps.campaigns.models import Campaign
        from apps.campaigns.tasks import process_recurring_campaigns

        now = timezone.now()
        due = Campaign.objects.filter(
            is_recurring_active=True,
            next_run__lte=now,
        ).order_by('next_run')

        if options['dry_run']:
            count = due.count()
            self.stdout.write(f'Due recurring campaigns: {count}')
            for campaign in due[:50]:
                self.stdout.write(
                    f'- #{campaign.id} {campaign.name} next_run={campaign.next_run} recurrence={campaign.recurrence}'
                )
            return

        old_always_eager = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        old_eager_propagates = getattr(settings, 'CELERY_TASK_EAGER_PROPAGATES', False)

        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = False
        try:
            result = process_recurring_campaigns()
        finally:
            settings.CELERY_TASK_ALWAYS_EAGER = old_always_eager
            settings.CELERY_TASK_EAGER_PROPAGATES = old_eager_propagates

        self.stdout.write(self.style.SUCCESS(str(result)))
