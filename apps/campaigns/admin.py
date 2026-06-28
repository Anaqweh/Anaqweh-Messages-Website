from django.contrib import admin
from .models import Campaign, EmailLog
admin.site.register(Campaign)
admin.site.register(EmailLog)


# تعريب أسماء النماذج (عرض فقط)
from .models import Campaign, EmailLog
for _m, (_s, _p) in {
    Campaign: ("حملة", "الحملات"),
    EmailLog: ("سجل إيميل", "سجلات الإيميل"),
}.items():
    _m._meta.verbose_name = _s
    _m._meta.verbose_name_plural = _p


# تعريب إضافي (عرض فقط)
try:
    from .models import CampaignMessageStep
    CampaignMessageStep._meta.verbose_name = "رسالة حملة"
    CampaignMessageStep._meta.verbose_name_plural = "رسائل الحملات"
except Exception:
    pass
