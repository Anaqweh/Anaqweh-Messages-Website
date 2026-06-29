from django.contrib import admin
from .models import Payment, Invoice, Expense, StripePayout, StripeWebhookEvent, CompanySettings


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_email', 'amount', 'currency', 'stripe_fee', 'net_amount', 'status', 'created_at')
    search_fields = ('customer_email', 'customer_name', 'stripe_checkout_session_id', 'stripe_payment_intent_id')
    list_filter = ('status', 'currency', 'source')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'payment', 'email_sent_at', 'opened_at', 'open_count', 'created_at')
    search_fields = ('invoice_number', 'payment__customer_email')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'amount', 'currency', 'spent_at', 'recurrence')
    list_filter = ('category', 'recurrence', 'currency')


@admin.register(StripePayout)
class StripePayoutAdmin(admin.ModelAdmin):
    list_display = ('payout_id', 'amount', 'currency', 'status', 'arrival_date', 'created_at')


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'event_type', 'processed', 'created_at')
    list_filter = ('event_type', 'processed')


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'email', 'phone', 'trn', 'updated_at')

    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================
# تعريب أسماء النماذج في لوحة الإدارة (عرض فقط - لا يمس المنطق)
# ============================================================
from .models import Payment, Invoice, Expense, StripePayout, StripeWebhookEvent, CompanySettings

_ar_names = {
    Payment: ("مدفوعة", "المدفوعات"),
    Invoice: ("فاتورة", "الفواتير"),
    Expense: ("مصروف", "المصروفات"),
    StripePayout: ("تحويل Stripe", "تحويلات Stripe"),
    StripeWebhookEvent: ("حدث Stripe", "أحداث Stripe"),
    CompanySettings: ("إعدادات الشركة", "إعدادات الشركة"),
}
for _model, (_singular, _plural) in _ar_names.items():
    _model._meta.verbose_name = _singular
    _model._meta.verbose_name_plural = _plural


# تعريب إضافي (عرض فقط)
try:
    from .models import SalesInvoiceItem
    SalesInvoiceItem._meta.verbose_name = "بند فاتورة"
    SalesInvoiceItem._meta.verbose_name_plural = "بنود الفواتير"
except Exception:
    pass


# تصميم الفاتورة في لوحة الإدارة
from .models import InvoiceBranding

@admin.register(InvoiceBranding)
class InvoiceBrandingAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'company_name_ar', 'primary_color', 'updated_at')
    search_fields = ('company_name_ar', 'company_name_en', 'tenant__name')
    list_filter = ('tenant',)
