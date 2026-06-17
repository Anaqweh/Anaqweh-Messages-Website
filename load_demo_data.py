from django.core.management.base import BaseCommand
from apps.templates_mgr.models import EmailTemplate
from apps.recipients.models import MailingList, Recipient


class Command(BaseCommand):
    help = 'Load sample demo data for testing'

    def handle(self, *args, **kwargs):
        # ── Email Templates ────────────────────────────────────────
        if not EmailTemplate.objects.exists():
            EmailTemplate.objects.create(
                name='قالب الترحيب',
                subject='مرحباً {{name}} – أهلاً بك في INEXC',
                body_html='''
<div style="font-family: Arial, sans-serif; direction: rtl; max-width: 600px; margin: auto; background: #f9f9f9; padding: 20px; border-radius: 12px;">
  <div style="background: linear-gradient(135deg, #1e3a6e, #2a5298); padding: 30px; border-radius: 10px; text-align: center;">
    <h1 style="color: white; margin: 0;">INEXC</h1>
    <p style="color: rgba(255,255,255,0.8); margin-top: 5px;">مرحباً بك!</p>
  </div>
  <div style="background: white; padding: 25px; border-radius: 10px; margin-top: 15px;">
    <h2 style="color: #1e3a6e;">مرحباً {{name}} 👋</h2>
    <p style="color: #555; line-height: 1.8;">
      يسعدنا انضمامك إلى منصة INEXC. تم تسجيلك بنجاح في <strong>{{course_name}}</strong>.
    </p>
    <p style="color: #555;">{{custom_message}}</p>
    <div style="text-align: center; margin-top: 25px;">
      <a href="#" style="background: #1e3a6e; color: white; padding: 12px 30px; border-radius: 8px; text-decoration: none; font-weight: bold;">
        ابدأ الآن
      </a>
    </div>
  </div>
  <p style="text-align: center; color: #aaa; font-size: 12px; margin-top: 15px;">
    © 2025 INEXC | <a href="/recipients/unsubscribe/{{email}}/" style="color: #aaa;">إلغاء الاشتراك</a>
  </p>
</div>
''',
                body_text='مرحباً {{name}}،\nتم تسجيلك في {{course_name}}.\n{{custom_message}}',
            )

            EmailTemplate.objects.create(
                name='قالب تذكير الدورة',
                subject='تذكير: دورة {{course_name}} تبدأ قريباً يا {{name}}',
                body_html='''
<div style="font-family: Arial, sans-serif; direction: rtl; max-width: 600px; margin: auto; padding: 20px;">
  <div style="background: #00b4d8; padding: 20px; border-radius: 10px; text-align: center;">
    <h2 style="color: white; margin: 0;">⏰ تذكير مهم</h2>
  </div>
  <div style="background: white; border: 1px solid #e2e8f0; padding: 25px; border-radius: 10px; margin-top: 10px;">
    <p style="color: #333; font-size: 16px;">عزيزنا <strong>{{name}}</strong>،</p>
    <p style="color: #555; line-height: 1.8;">
      نود تذكيرك بأن <strong>{{course_name}}</strong> ستنطلق قريباً. 
      يرجى التأكد من استعدادك والحضور في الوقت المحدد.
    </p>
    <p style="color: #555;">{{custom_message}}</p>
    <p style="color: #888; font-size: 12px; margin-top: 20px;">
      للاستفسار تواصل معنا على: info@inexc.com | هاتف: {{phone}}
    </p>
  </div>
</div>
''',
                body_text='عزيزنا {{name}}، تذكير بدورة {{course_name}}.\n{{custom_message}}',
            )
            self.stdout.write(self.style.SUCCESS('✅ تم إنشاء القوالب التجريبية'))

        # ── Mailing List + Recipients ───────────────────────────────
        if not MailingList.objects.exists():
            ml = MailingList.objects.create(
                name='قائمة الاختبار',
                description='قائمة تجريبية للتطوير والاختبار',
            )

            demo_recipients = [
                ('أحمد محمد', 'ahmed@example.com', '0501111111', 'دورة Python'),
                ('سارة علي',  'sara@example.com',  '0502222222', 'دورة Data Science'),
                ('محمد خالد', 'mhd@example.com',   '0503333333', 'دورة Web Dev'),
                ('نورة أحمد', 'noura@example.com', '0504444444', 'دورة AI'),
                ('عمر يوسف',  'omar@example.com',  '0505555555', 'دورة Python'),
            ]

            for name, email, phone, course in demo_recipients:
                Recipient.objects.create(
                    mailing_list=ml,
                    name=name,
                    email=email,
                    phone=phone,
                    custom_field_1=course,
                    custom_field_2='نتمنى لك تجربة رائعة مع INEXC',
                )

            self.stdout.write(self.style.SUCCESS(
                f'✅ تم إنشاء القائمة التجريبية بـ {len(demo_recipients)} مستلمين'
            ))
        else:
            self.stdout.write(self.style.WARNING('⚠️  البيانات التجريبية موجودة مسبقاً'))
