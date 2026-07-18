from django.conf import settings
from django.db import models


def default_registration_schema():
    return {
        "sections": [
            {
                "title": "Personal Information",
                "title_ar": "المعلومات الشخصية",
                "fields": [
                    {"name": "full_name", "label": "Full name", "label_ar": "الاسم الكامل", "type": "text", "required": True},
                    {"name": "mobile", "label": "Mobile Number", "label_ar": "رقم الهاتف", "type": "text", "required": True},
                    {"name": "email", "label": "Email", "label_ar": "البريد الإلكتروني", "type": "email", "required": True},
                    {"name": "nationality", "label": "Nationality", "label_ar": "الجنسية", "type": "text", "required": False},
                    {"name": "date_of_birth", "label": "Date of Birth", "label_ar": "تاريخ الميلاد", "type": "date", "required": False},
                ],
            }
        ]
    }


class RegistrationFormTemplate(models.Model):
    tenant = models.ForeignKey(
        "platform_core.Tenant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_templates",
    )
    name = models.CharField(max_length=180, default="Spark Language Institute")
    header_title = models.CharField(max_length=180, blank=True, default="")
    header_subtitle = models.CharField(max_length=220, blank=True, default="Registration Form - One to One (VIP)")
    logo = models.FileField(upload_to="registration_logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    schema = models.JSONField(default=default_registration_schema, blank=True)
    terms_text = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_form_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class RegistrationSubmission(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("reviewed", "Reviewed"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    tenant = models.ForeignKey(
        "platform_core.Tenant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_submissions",
    )
    template = models.ForeignKey(
        RegistrationFormTemplate,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")
    data = models.JSONField(default=dict, blank=True)
    student_name = models.CharField(max_length=180, blank=True, default="")
    student_email = models.EmailField(blank=True, default="")
    signature_data = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registration_submissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    email_sent_at = models.DateTimeField(null=True, blank=True)
    admin_notified = models.BooleanField(default=False)
    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.student_name or f"Registration #{self.pk}"


class RegEmployee(models.Model):
    """موظف متابعة العملاء — لكل شركة موظفوها."""
    tenant = models.ForeignKey('platform_core.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='reg_employees')
    name = models.CharField("اسم الموظف", max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "موظف متابعة"
        verbose_name_plural = "موظفو المتابعة"

    def __str__(self):
        return self.name


class RegClient(models.Model):
    """عميل متابعة في قسم التسجيلات — معزول لكل شركة."""
    STATUS_CHOICES = [
        ("potential", "عميل محتمل"),
        ("followup", "متابعة"),
        ("deposit", "دفعة مدفوعة"),
        ("registered", "تم التسجيل"),
        ("client", "عميل"),
        ("not_interested", "غير مهتم"),
    ]
    tenant = models.ForeignKey('platform_core.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='reg_clients')
    name = models.CharField("الاسم", max_length=160)
    phone = models.CharField("رقم الجوال", max_length=40)
    status = models.CharField("حالة العميل", max_length=20, choices=STATUS_CHOICES, default="potential")
    employee = models.ForeignKey(RegEmployee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="اسم الموظف", related_name="clients")
    notes = models.TextField("ملاحظات", blank=True)
    reminder_date = models.DateField("تاريخ التذكير", null=True, blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reg_clients_created', verbose_name="أضافه")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "عميل متابعة"
        verbose_name_plural = "عملاء المتابعة"

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
