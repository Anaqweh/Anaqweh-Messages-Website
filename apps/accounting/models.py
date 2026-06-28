from decimal import Decimal
from django.db import models
from django.utils import timezone


class Customer(models.Model):
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="accounting_customers")
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


# ============================================================
# نظام رواتب الموظفين (HR + Payroll)
# ============================================================

class Employee(models.Model):
    STATUS_CHOICES = [
        ('active', 'على رأس العمل'),
        ('terminated', 'منتهي الخدمة'),
    ]
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="employees")
    full_name = models.CharField('الاسم الكامل', max_length=200)
    national_id = models.CharField('رقم الهوية/الإقامة', max_length=50, blank=True, db_index=True)
    id_expiry = models.DateField('تاريخ انتهاء الهوية', null=True, blank=True)
    job_title = models.CharField('المسمى الوظيفي', max_length=150, blank=True)
    hire_date = models.DateField('تاريخ التعيين', null=True, blank=True)
    base_salary = models.DecimalField('الراتب الأساسي', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    allowances = models.DecimalField('البدلات', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deductions = models.DecimalField('الخصومات الثابتة', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    iban = models.CharField('رقم الآيبان', max_length=50, blank=True)
    phone = models.CharField('الجوال', max_length=50, blank=True)
    email = models.EmailField('البريد', blank=True)
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']
        verbose_name = 'موظف'
        verbose_name_plural = 'الموظفون'

    def __str__(self):
        return self.full_name

    @property
    def net_salary(self):
        return (self.base_salary or Decimal('0')) + (self.allowances or Decimal('0')) - (self.deductions or Decimal('0'))

    @property
    def id_status(self):
        """حالة الهوية: expired / soon / ok / unknown"""
        if not self.id_expiry:
            return 'unknown'
        from datetime import date, timedelta
        today = date.today()
        if self.id_expiry < today:
            return 'expired'
        if self.id_expiry <= today + timedelta(days=30):
            return 'soon'
        return 'ok'

    @property
    def id_days_left(self):
        if not self.id_expiry:
            return None
        from datetime import date
        return (self.id_expiry - date.today()).days


class PayrollRun(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('approved', 'معتمد'),
        ('paid', 'مدفوع'),
    ]
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="payroll_runs")
    year = models.IntegerField('السنة')
    month = models.IntegerField('الشهر')
    status = models.CharField('الحالة', max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField('إجمالي الرواتب', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    expense_id = models.IntegerField('معرّف المصروف المرتبط', null=True, blank=True)
    notes = models.TextField('ملاحظات', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month']
        verbose_name = 'مسير رواتب'
        verbose_name_plural = 'مسيرات الرواتب'
        unique_together = [('tenant', 'year', 'month')]

    MONTH_NAMES = ['', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']

    def __str__(self):
        return f'مسير {self.month_name} {self.year}'

    @property
    def month_name(self):
        try:
            return self.MONTH_NAMES[self.month]
        except (IndexError, TypeError):
            return str(self.month)

    def recalculate_total(self):
        from django.db.models import Sum
        total = self.payslips.aggregate(s=Sum('net'))['s'] or Decimal('0.00')
        self.total_amount = total
        self.save(update_fields=['total_amount', 'updated_at'])
        return total


class Payslip(models.Model):
    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='payslips')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payslips')
    base_salary = models.DecimalField('الأساسي', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    allowances = models.DecimalField('البدلات', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deductions = models.DecimalField('الخصومات', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net = models.DecimalField('الصافي', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    notes = models.CharField('ملاحظات', max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['employee__full_name']
        verbose_name = 'قسيمة راتب'
        verbose_name_plural = 'قسائم الرواتب'

    def __str__(self):
        return f'{self.employee.full_name} - {self.payroll_run}'

    def save(self, *args, **kwargs):
        self.net = (self.base_salary or Decimal('0')) + (self.allowances or Decimal('0')) - (self.deductions or Decimal('0'))
        super().save(*args, **kwargs)
