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
