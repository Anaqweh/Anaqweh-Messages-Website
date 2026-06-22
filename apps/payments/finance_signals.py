from django.db.models.signals import pre_save
from django.dispatch import receiver

from apps.platform_core.tenant_context import get_current_tenant

from .models import Expense, Invoice, Payment, SalesInvoice


def _assign_current_tenant(instance):
    if not hasattr(instance, "tenant_id"):
        return

    if instance.tenant_id:
        return

    tenant = get_current_tenant()
    if tenant:
        instance.tenant = tenant


@receiver(pre_save, sender=Payment)
def assign_payment_tenant(sender, instance, **kwargs):
    _assign_current_tenant(instance)


@receiver(pre_save, sender=Invoice)
def assign_invoice_tenant(sender, instance, **kwargs):
    _assign_current_tenant(instance)


@receiver(pre_save, sender=Expense)
def assign_expense_tenant(sender, instance, **kwargs):
    _assign_current_tenant(instance)


@receiver(pre_save, sender=SalesInvoice)
def assign_sales_invoice_tenant(sender, instance, **kwargs):
    _assign_current_tenant(instance)
