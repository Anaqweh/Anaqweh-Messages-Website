import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


class Payment(models.Model):
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="finance_payments")
    STATUS_CHOICES = [
        ('pending', 'بانتظار الدفع'),
        ('paid', 'مدفوع'),
        ('failed', 'فشل'),
        ('refunded', 'مسترد'),
        ('disputed', 'نزاع'),
    ]

    source = models.CharField(max_length=80, default='email_payment')
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField(blank=True)
    description = models.CharField(max_length=300, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default='aed')
    stripe_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_balance_transaction_id = models.CharField(max_length=255, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer_email or self.customer_name or "Payment"} - {self.amount} {self.currency}'

    @property
    def profit_amount(self):
        return (self.net_amount or Decimal('0.00'))


class Invoice(models.Model):
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="finance_invoices")
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='invoice')
    invoice_number = models.CharField(max_length=40, unique=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    company_name = models.CharField(max_length=200, default='شركة التميز الابتكاري')
    email_sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    open_count = models.PositiveIntegerField(default=0)
    last_open_ip = models.CharField(max_length=80, blank=True)
    last_open_user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = timezone.now().year
            next_id = (Invoice.objects.count() + 1)
            self.invoice_number = f'TMZ-{year}-{next_id:06d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number


class Expense(models.Model):
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="finance_expenses")
    CATEGORY_CHOICES = [
        ('trainer', 'مدرب'),
        ('zoom', 'Zoom'),
        ('ads', 'إعلانات'),
        ('design', 'تصميم'),
        ('tools', 'أدوات'),
        ('transfer', 'رسوم تحويل'),
        ('other', 'أخرى'),
    ]

    RECURRENCE_CHOICES = [
        ('none', 'غير متكرر'),
        ('daily', 'يومي'),
        ('weekly', 'أسبوعي'),
        ('monthly', 'شهري'),
        ('yearly', 'سنوي'),
    ]

    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='aed')
    spent_at = models.DateField(default=timezone.localdate)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='none')
    notes = models.TextField(blank=True)
    attachment = models.FileField('مرفق', upload_to='expenses/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-spent_at', '-created_at']

    def __str__(self):
        return f'{self.title} - {self.amount} {self.currency}'


class StripePayout(models.Model):
    payout_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default='aed')
    status = models.CharField(max_length=40, blank=True)
    arrival_date = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class StripeWebhookEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=120)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class CompanySettings(models.Model):
    name_ar = models.CharField(max_length=300, default='شركة التميز الابتكاري لتصميم نظم الحاسب الآلي التعليمية والتدريبية')
    name_en = models.CharField(max_length=300, blank=True, default='ALTMYZ ALABTKARY FOR EDUCATION & TRAINING COMPUTER SOFTWARE CO')
    email = models.EmailField(blank=True, default='info@inexc.com')
    phone = models.CharField(max_length=50, blank=True, default='+971543475500')
    website = models.CharField(max_length=120, blank=True, default='www.inexc.com')
    address = models.CharField(max_length=300, blank=True)
    trn = models.CharField('الرقم الضريبي', max_length=50, blank=True, default='104863757100001')
    license_no = models.CharField('رقم الرخصة', max_length=50, blank=True, default='1393230')
    logo = models.ImageField(upload_to='company/', blank=True, null=True)
    stamp = models.ImageField(upload_to='company/', blank=True, null=True)
    signature = models.ImageField(upload_to='company/', blank=True, null=True)
    invoice_footer = models.TextField(blank=True, default='شكراً لتعاملكم معنا')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إعدادات الشركة'
        verbose_name_plural = 'إعدادات الشركة'

    def __str__(self):
        return self.name_ar or 'إعدادات الشركة'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SalesInvoice(models.Model):
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="finance_sales_invoices")
    KIND_CHOICES = [
        ('sales', 'فاتورة مبيعات'),
        ('due', 'فاتورة مستحقة'),
        ('purchase', 'فاتورة شراء'),
        ('receipt', 'سند قبض'),
        ('payment', 'سند صرف'),
        ('quote', 'عرض سعر'),
    ]
    # إعدادات كل نوع: (العنوان بالإنجليزية، بادئة الرقم، هل يظهر كمستحق)
    KIND_META = {
        'sales':    {'title': 'INVOICE',     'prefix': 'SAL', 'doc_ar': 'فاتورة مبيعات'},
        'due':      {'title': 'INVOICE',     'prefix': 'DUE', 'doc_ar': 'فاتورة مستحقة'},
        'purchase': {'title': 'PURCHASE',    'prefix': 'PUR', 'doc_ar': 'فاتورة شراء'},
        'receipt':  {'title': 'RECEIPT',     'prefix': 'RCV', 'doc_ar': 'سند قبض'},
        'payment':  {'title': 'PAYMENT',     'prefix': 'PAY', 'doc_ar': 'سند صرف'},
        'quote':    {'title': 'QUOTATION',   'prefix': 'QUO', 'doc_ar': 'عرض سعر'},
    }
    STATUS_CHOICES = [
        ('unpaid', 'غير مدفوعة'),
        ('paid', 'مدفوعة'),
        ('cancelled', 'ملغاة'),
    ]
    PAYMENT_METHODS = [
        ('cash', 'نقدي'),
        ('cheque', 'شيك'),
        ('bank', 'تحويل بنكي'),
        ('card', 'بطاقة / Stripe'),
        ('other', 'أخرى'),
    ]
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default='sales')
    invoice_number = models.CharField(max_length=40, unique=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_address = models.CharField(max_length=300, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    payment_ref = models.CharField('مرجع الدفع (رقم شيك/تحويل)', max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='unpaid')
    currency = models.CharField(max_length=10, default='aed')
    tax_rate = models.DecimalField('نسبة الضريبة %', max_digits=5, decimal_places=2, default=Decimal('5.00'))
    notes = models.TextField(blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'فاتورة'
        verbose_name_plural = 'الفواتير الإلكترونية'

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = timezone.localdate().year
            meta = self.KIND_META.get(self.kind, self.KIND_META['sales'])
            prefix = meta['prefix']
            base = f'{prefix}-{year}-'
            # نعتمد على أعلى رقم موجود فعلاً (لا على العدّ) لتجنّب التكرار بعد الحذف
            existing = SalesInvoice.objects.filter(
                invoice_number__startswith=base
            ).values_list('invoice_number', flat=True)
            max_seq = 0
            for num in existing:
                tail = num.replace(base, '', 1)
                if tail.isdigit():
                    max_seq = max(max_seq, int(tail))
            # حلقة أمان: نزيد حتى نجد رقماً غير مستخدم
            seq = max_seq + 1
            while SalesInvoice.objects.filter(invoice_number=f'{base}{seq:04d}').exists():
                seq += 1
            self.invoice_number = f'{base}{seq:04d}'
        super().save(*args, **kwargs)

    @property
    def doc_title(self):
        """العنوان الإنجليزي للمستند حسب نوعه."""
        return self.KIND_META.get(self.kind, {}).get('title', 'INVOICE')

    @property
    def doc_title_ar(self):
        """العنوان العربي للمستند حسب نوعه."""
        return self.KIND_META.get(self.kind, {}).get('doc_ar', 'فاتورة')

    @property
    def subtotal(self):
        return sum((it.line_total for it in self.items.all()), Decimal('0.00'))

    @property
    def tax_amount(self):
        return (self.subtotal * self.tax_rate / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def total(self):
        return (self.subtotal + self.tax_amount).quantize(Decimal('0.01'))

    @property
    def cost_total(self):
        return sum((it.cost_total for it in self.items.all()), Decimal('0.00')).quantize(Decimal('0.01'))

    @property
    def gross_profit(self):
        return (self.subtotal - self.cost_total).quantize(Decimal('0.01'))

    @property
    def margin_percent(self):
        if not self.subtotal:
            return Decimal('0.00')
        return (self.gross_profit * Decimal('100') / self.subtotal).quantize(Decimal('0.01'))

    def __str__(self):
        return self.invoice_number or 'فاتورة'


class SalesInvoiceItem(models.Model):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1'))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    @property
    def line_total(self):
        return (self.quantity * self.unit_price).quantize(Decimal('0.01'))

    @property
    def cost_total(self):
        return (self.quantity * self.unit_cost).quantize(Decimal('0.01'))

    @property
    def gross_profit(self):
        return (self.line_total - self.cost_total).quantize(Decimal('0.01'))

    def __str__(self):
        return self.description[:40]


class InvoiceBranding(models.Model):
    """تصميم فاتورة المبيعات الخاص بكل شركة (شعار، ألوان، توقيع) - معزول لكل tenant."""
    tenant = models.OneToOneField(
        "platform_core.Tenant",
        on_delete=models.CASCADE,
        related_name="invoice_branding",
    )
    # الهوية البصرية
    logo = models.ImageField('الشعار', upload_to='invoice_branding/', blank=True, null=True)
    signature = models.ImageField('التوقيع', upload_to='invoice_branding/', blank=True, null=True)
    stamp = models.ImageField('الختم', upload_to='invoice_branding/', blank=True, null=True)
    # الألوان
    primary_color = models.CharField('اللون الرئيسي', max_length=9, default='#0b4ea2')
    secondary_color = models.CharField('اللون الثانوي', max_length=9, default='#1565c0')
    text_color = models.CharField('لون النص', max_length=9, default='#1f2937')
    # بيانات الشركة على الفاتورة
    company_name_ar = models.CharField('اسم الشركة (عربي)', max_length=300, blank=True, default='')
    company_name_en = models.CharField('اسم الشركة (إنجليزي)', max_length=300, blank=True, default='')
    email = models.EmailField('البريد', blank=True, default='')
    phone = models.CharField('الهاتف', max_length=50, blank=True, default='')
    website = models.CharField('الموقع', max_length=120, blank=True, default='')
    address = models.CharField('العنوان', max_length=300, blank=True, default='')
    trn = models.CharField('الرقم الضريبي', max_length=50, blank=True, default='')
    license_no = models.CharField('رقم الرخصة', max_length=50, blank=True, default='')
    invoice_footer = models.TextField('تذييل الفاتورة', blank=True, default='شكراً لتعاملكم معنا')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تصميم فاتورة'
        verbose_name_plural = 'تصاميم الفواتير'

    def __str__(self):
        return f"تصميم فاتورة - {self.tenant.name if self.tenant else ''}"

    @classmethod
    def for_tenant(cls, tenant):
        """يجلب أو ينشئ تصميم الفاتورة للشركة."""
        if tenant is None:
            return None
        obj, _ = cls.objects.get_or_create(tenant=tenant)
        return obj
