from decimal import Decimal
from django.db import models
from django.utils import timezone


class Customer(models.Model):
    name = models.CharField('الاسم', max_length=200)
    email = models.EmailField('البريد', blank=True, db_index=True)
    phone = models.CharField('الهاتف', max_length=50, blank=True)
    company = models.CharField('الشركة/الجهة', max_length=200, blank=True)
    address = models.CharField('العنوان', max_length=300, blank=True)
    trn = models.CharField('الرقم الضريبي', max_length=50, blank=True)
    notes = models.TextField('ملاحظات', blank=True)
    is_active = models.BooleanField('نشط', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'عميل'
        verbose_name_plural = 'العملاء'

    def __str__(self):
        return self.name

    def _sales_invoices(self):
        """قراءة فقط من جداول الفواتير الموجودة - لا تعديل."""
        from apps.payments.models import SalesInvoice
        qs = SalesInvoice.objects.all()
        if self.email:
            return qs.filter(customer_email__iexact=self.email)
        return qs.filter(customer_name=self.name)

    @property
    def total_paid(self):
        total = Decimal('0.00')
        for inv in self._sales_invoices().filter(status='paid'):
            total += inv.total
        return total

    @property
    def total_due(self):
        total = Decimal('0.00')
        for inv in self._sales_invoices().filter(status='unpaid'):
            total += inv.total
        return total

    @property
    def invoice_count(self):
        return self._sales_invoices().count()
