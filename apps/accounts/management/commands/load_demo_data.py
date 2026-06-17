from django.core.management.base import BaseCommand
from apps.templates_mgr.models import EmailTemplate
from apps.recipients.models import MailingList, Recipient
class Command(BaseCommand):
    help = 'Load demo data'
    def handle(self, *args, **kwargs):
        if not EmailTemplate.objects.exists():
            EmailTemplate.objects.create(
                name='قالب الترحيب',
                subject='مرحباً {{name}}',
                body_html='<p>مرحباً {{name}}، تم تسجيلك في {{course_name}}</p>',
                body_text='مرحباً {{name}}',
            )
            self.stdout.write(self.style.SUCCESS('✅ Templates created'))
        if not MailingList.objects.exists():
            ml = MailingList.objects.create(name='قائمة الاختبار')
            Recipient.objects.create(mailing_list=ml, name='أحمد محمد', email='ahmed@example.com', phone='0501111111', custom_field_1='دورة Python')
            self.stdout.write(self.style.SUCCESS('✅ Demo data created'))
