from django.contrib import admin
from .models import EmailTemplate
admin.site.register(EmailTemplate)


# تعريب أسماء النماذج (عرض فقط)
from .models import EmailTemplate
EmailTemplate._meta.verbose_name = "قالب بريدي"
EmailTemplate._meta.verbose_name_plural = "القوالب البريدية"


# تعريب إضافي (عرض فقط)
try:
    from .models import BankPaymentPage
    BankPaymentPage._meta.verbose_name = "صفحة دفع بنكي"
    BankPaymentPage._meta.verbose_name_plural = "صفحات الدفع البنكي"
except Exception:
    pass
