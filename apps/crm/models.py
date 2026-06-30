from django.conf import settings
from django.db import models
from django.utils import timezone

class CRMCompany(models.Model):
    STATUS_CHOICES = [("lead","عميل محتمل"),("customer","عميل فعلي"),("inactive","غير نشط"),("lost","مفقود")]
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_companies")
    name = models.CharField(max_length=180)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="lead")
    source = models.CharField(max_length=120, blank=True)
    industry = models.CharField(max_length=120, blank=True)
    website = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    country = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    trn = models.CharField(max_length=80, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_companies")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-updated_at", "name"]
    def __str__(self):
        return self.name

class CRMContact(models.Model):
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_contacts")
    company = models.ForeignKey(CRMCompany, null=True, blank=True, on_delete=models.SET_NULL, related_name="contacts")
    full_name = models.CharField(max_length=180)
    job_title = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    whatsapp = models.CharField(max_length=60, blank=True)
    source = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_contacts")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-updated_at", "full_name"]
    def __str__(self):
        return self.full_name

class CRMDeal(models.Model):
    STAGE_CHOICES = [("new","فرصة جديدة"),("contacted","تم التواصل"),("proposal","عرض سعر"),("negotiation","تفاوض"),("won","تم الفوز"),("lost","تم الفقد")]
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_deals")
    company = models.ForeignKey(CRMCompany, null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    contact = models.ForeignKey(CRMContact, null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    title = models.CharField(max_length=180)
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default="new")
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="AED")
    probability = models.PositiveIntegerField(default=20)
    expected_close_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_deals")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-updated_at", "title"]
    def __str__(self):
        return self.title

class CRMTask(models.Model):
    TYPE_CHOICES = [("call","اتصال"),("email","بريد"),("meeting","اجتماع"),("follow_up","متابعة"),("payment","متابعة دفع"),("other","أخرى")]
    STATUS_CHOICES = [("open","مفتوحة"),("done","منجزة"),("cancelled","ملغية")]
    PRIORITY_CHOICES = [("low","منخفضة"),("normal","عادية"),("high","عالية"),("urgent","عاجلة")]
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_tasks")
    company = models.ForeignKey(CRMCompany, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    contact = models.ForeignKey(CRMContact, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    deal = models.ForeignKey(CRMDeal, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    title = models.CharField(max_length=180)
    task_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="follow_up")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")
    due_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_tasks")
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["status", "due_at", "-created_at"]
    def mark_done(self):
        self.status = "done"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])
    def __str__(self):
        return self.title


class CRMQuote(models.Model):
    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("sent", "مرسل"),
        ("accepted", "مقبول"),
        ("rejected", "مرفوض"),
        ("expired", "منتهي"),
    ]
    tenant = models.ForeignKey("platform_core.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_quotes")
    company = models.ForeignKey(CRMCompany, null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    contact = models.ForeignKey(CRMContact, null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    deal = models.ForeignKey(CRMDeal, null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    quote_number = models.CharField(max_length=40, unique=True, blank=True)
    title = models.CharField(max_length=180)
    customer_email = models.EmailField("بريد العميل", blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    currency = models.CharField(max_length=10, default="AED")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="crm_quotes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "عرض سعر"
        verbose_name_plural = "عروض الأسعار"

    def save(self, *args, **kwargs):
        if not self.quote_number:
            year = timezone.now().year
            last = CRMQuote.objects.filter(quote_number__startswith=f"QTE-{year}-").count()
            self.quote_number = f"QTE-{year}-{last + 1:04d}"
        super().save(*args, **kwargs)

    def recalc(self):
        from decimal import Decimal
        sub = sum((i.line_total for i in self.items.all()), Decimal("0.00"))
        tax = (sub * self.tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        self.subtotal = sub
        self.tax_amount = tax
        self.total = sub + tax
        self.save(update_fields=["subtotal", "tax_amount", "total"])

    def __str__(self):
        return self.quote_number or self.title


class CRMQuoteItem(models.Model):
    quote = models.ForeignKey(CRMQuote, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    @property
    def line_total(self):
        from decimal import Decimal
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    def __str__(self):
        return self.description[:40]
