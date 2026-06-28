from django.contrib import admin

from .models import CRMCompany, CRMContact, CRMDeal, CRMTask


@admin.register(CRMCompany)
class CRMCompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "email", "phone", "tenant", "owner", "updated_at")
    list_filter = ("status", "tenant")
    search_fields = ("name", "email", "phone", "trn")


@admin.register(CRMContact)
class CRMContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company", "email", "phone", "tenant", "owner", "updated_at")
    list_filter = ("tenant",)
    search_fields = ("full_name", "email", "phone", "company__name")


@admin.register(CRMDeal)
class CRMDealAdmin(admin.ModelAdmin):
    list_display = ("title", "stage", "value", "currency", "company", "owner", "updated_at")
    list_filter = ("stage", "tenant")
    search_fields = ("title", "company__name", "contact__full_name")


@admin.register(CRMTask)
class CRMTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "priority", "task_type", "due_at", "assigned_to", "tenant")
    list_filter = ("status", "priority", "task_type", "tenant")
    search_fields = ("title", "notes")


# تعريب أسماء النماذج في لوحة الإدارة (عرض فقط)
from .models import CRMCompany, CRMContact, CRMDeal, CRMTask
_ar = {
    CRMCompany: ("شركة", "الشركات"),
    CRMContact: ("جهة اتصال", "جهات الاتصال"),
    CRMDeal: ("صفقة", "الصفقات"),
    CRMTask: ("مهمة", "المهام"),
}
for _m, (_s, _p) in _ar.items():
    _m._meta.verbose_name = _s
    _m._meta.verbose_name_plural = _p


# تعريب إضافي (عرض فقط)
try:
    from .models import CRMQuoteItem
    CRMQuoteItem._meta.verbose_name = "بند عرض سعر"
    CRMQuoteItem._meta.verbose_name_plural = "بنود عروض الأسعار"
except Exception:
    pass
