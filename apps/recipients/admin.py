from django.contrib import admin
from .models import MailingList, Recipient, UnsubscribeList, UploadBatch
admin.site.register(MailingList)
admin.site.register(Recipient)
admin.site.register(UnsubscribeList)
admin.site.register(UploadBatch)


# تعريب أسماء النماذج في لوحة الإدارة (عرض فقط)
from .models import MailingList, Recipient, UnsubscribeList, UploadBatch
_ar = {
    MailingList: ("قائمة بريدية", "القوائم البريدية"),
    Recipient: ("مستلم", "المستلمون"),
    UnsubscribeList: ("إلغاء اشتراك", "قائمة إلغاء الاشتراك"),
    UploadBatch: ("دفعة رفع", "دفعات الرفع"),
}
for _m, (_s, _p) in _ar.items():
    _m._meta.verbose_name = _s
    _m._meta.verbose_name_plural = _p
