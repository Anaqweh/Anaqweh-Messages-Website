from django.conf import settings
from django.db import models


def default_tenant_modules():
    return {
        "email": True,
        "finance": True,
        "crm": False,
        "accounting": True,
        "reports": True,
        "tasks": False,
        "registrations": False,
        "stripe": False,
    }


def default_tenant_limits():
    return {
        "users": 5,
        "campaigns_per_month": 100,
        "contacts": 5000,
        "invoices_per_month": 500,
        "storage_mb": 1024,
    }


def default_permissions():
    return {
        "email": {"view": True, "create": False, "edit": False, "delete": False, "send": False},
        "finance": {"view": False, "create": False, "edit": False, "delete": False, "export": False},
        "accounting": {"view": False, "create": False, "edit": False, "delete": False, "export": False, "payroll": False},
        "crm": {"view": False, "create": False, "edit": False, "delete": False, "export": False},
        "reports": {"view": False, "export": False},
        "settings": {"view": False, "edit": False, "manage_users": False},
        "registrations": {
            "forms": {"spark": False},"view": False, "create": False, "edit": False, "delete": False, "settings": False},
        "stripe": {"view": False, "settings": False, "payouts": False},
        "emailjs": {"view": False, "edit": False},
    }


class ModuleCatalog(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name_ar = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "code"]

    def __str__(self):
        return self.name_ar or self.code


class Tenant(models.Model):
    STATUS_TRIAL = "trial"
    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_TRIAL, "تجريبي"),
        (STATUS_ACTIVE, "نشط"),
        (STATUS_SUSPENDED, "موقوف"),
        (STATUS_CANCELLED, "ملغي"),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=80, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    owner_name = models.CharField(max_length=180, blank=True)
    owner_email = models.EmailField(blank=True)
    owner_phone = models.CharField(max_length=50, blank=True)

    domain = models.CharField(max_length=180, blank=True)
    plan_name = models.CharField(max_length=80, blank=True)

    modules = models.JSONField(default=default_tenant_modules)
    limits = models.JSONField(default=default_tenant_limits)

    notes = models.TextField(blank=True)
    subscription_starts_at = models.DateField(null=True, blank=True)
    subscription_ends_at = models.DateField(null=True, blank=True)
    emailjs_service_id = models.CharField(max_length=100, blank=True, default="")
    emailjs_template_id = models.CharField(max_length=100, blank=True, default="")
    emailjs_public_key = models.CharField(max_length=100, blank=True, default="")
    emailjs_private_key = models.CharField(max_length=100, blank=True, default="")
    registration_admin_email = models.EmailField(blank=True, default="")

    # ===== خدمة Stripe =====
    STRIPE_MODE_PLATFORM = "platform"   # حساب المدير العام
    STRIPE_MODE_OWN = "own"             # حساب الشركة الخاص
    STRIPE_MODE_CHOICES = [
        (STRIPE_MODE_PLATFORM, "حساب المدير العام"),
        (STRIPE_MODE_OWN, "حساب الشركة الخاص"),
    ]
    stripe_enabled = models.BooleanField(default=False)
    stripe_mode = models.CharField(max_length=20, choices=STRIPE_MODE_CHOICES, default=STRIPE_MODE_PLATFORM)
    stripe_secret_key = models.CharField(max_length=255, blank=True, default="")
    stripe_publishable_key = models.CharField(max_length=255, blank=True, default="")
    stripe_webhook_secret = models.CharField(max_length=255, blank=True, default="")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # ===== بيانات الحساب البنكي (للتحويل اليدوي) =====
    bank_name = models.CharField(max_length=180, blank=True, default="")
    bank_country = models.CharField(max_length=100, blank=True, default="")
    bank_account_holder = models.CharField(max_length=180, blank=True, default="")
    bank_iban = models.CharField(max_length=100, blank=True, default="")
    bank_account_number = models.CharField(max_length=100, blank=True, default="")
    bank_swift = models.CharField(max_length=50, blank=True, default="")
    bank_currency = models.CharField(max_length=10, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name



class TenantRole(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="roles")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=default_permissions)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "name")]
        ordering = ["tenant__name", "name"]

    def __str__(self):
        return f"{self.name} - {self.tenant}"


class TenantMembership(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_memberships")

    role = models.ForeignKey(TenantRole, null=True, blank=True, on_delete=models.SET_NULL, related_name="memberships")
    role_name = models.CharField(max_length=80, blank=True)
    is_tenant_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    permissions = models.JSONField(default=default_permissions)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "user")]
        ordering = ["tenant__name", "user__username"]

    def __str__(self):
        return f"{self.user} @ {self.tenant}"


class PlatformAuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL)

    action = models.CharField(max_length=120)
    target_model = models.CharField(max_length=120, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.created_at:%Y-%m-%d %H:%M}"


class PlatformSettings(models.Model):
    """إعدادات المنصة العامة (يديرها المدير العام)."""
    commission_platform_stripe = models.DecimalField(max_digits=5, decimal_places=2, default=7)
    commission_own_stripe = models.DecimalField(max_digits=5, decimal_places=2, default=2)
    payout_hold_days = models.IntegerField(default=12)
    express_payout_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "إعدادات المنصة"

    def __str__(self):
        return "إعدادات المنصة"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj


class PayoutRequest(models.Model):
    """طلب سحب أموال من الشركة إلى المدير العام."""
    TYPE_NORMAL = "normal"
    TYPE_EXPRESS = "express"
    TYPE_CHOICES = [
        (TYPE_NORMAL, "عادي"),
        (TYPE_EXPRESS, "سريع (24-48 ساعة)"),
    ]
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "قيد المراجعة"),
        (STATUS_PAID, "تم التحويل"),
        (STATUS_REJECTED, "مرفوض"),
    ]
    tenant = models.ForeignKey("platform_core.Tenant", on_delete=models.CASCADE, related_name="payout_requests")
    requested_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    payout_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_NORMAL)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.TextField(blank=True, default="")
    transfer_reference = models.CharField(max_length=200, blank=True, default="")
    transfer_receipt = models.ImageField(upload_to="payout_receipts/", null=True, blank=True)
    transfer_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant.name} - {self.net_amount} ({self.get_status_display()})"


class SubscriptionPlan(models.Model):
    """باقات الاشتراك في المنصة."""
    name = models.CharField("اسم الباقة", max_length=80)
    price_monthly = models.DecimalField("السعر الشهري", max_digits=10, decimal_places=2, default=0)
    currency = models.CharField("العملة", max_length=10, default="AED")
    description = models.TextField("الوصف/المزايا", blank=True)
    is_active = models.BooleanField("متاحة", default=True)
    sort_order = models.PositiveIntegerField("الترتيب", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "price_monthly"]
        verbose_name = "باقة اشتراك"
        verbose_name_plural = "باقات الاشتراك"

    def __str__(self):
        return f"{self.name} ({self.price_monthly} {self.currency}/شهر)"


class TenantSubscription(models.Model):
    """اشتراك شركة في باقة."""
    STATUS_CHOICES = [
        ("active", "نشط"),
        ("expired", "منتهي"),
        ("cancelled", "ملغي"),
    ]
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="subscription", verbose_name="الشركة")
    plan = models.ForeignKey(SubscriptionPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="subscriptions", verbose_name="الباقة")
    start_date = models.DateField("بداية الاشتراك")
    end_date = models.DateField("نهاية الاشتراك")
    status = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default="active")
    notes = models.TextField("ملاحظات", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["end_date"]
        verbose_name = "اشتراك شركة"
        verbose_name_plural = "اشتراكات الشركات"

    def __str__(self):
        return f"{self.tenant.name} — {self.plan.name if self.plan else 'بلا باقة'} (حتى {self.end_date})"

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.end_date < timezone.localdate()

    @property
    def days_left(self):
        from django.utils import timezone
        return (self.end_date - timezone.localdate()).days
