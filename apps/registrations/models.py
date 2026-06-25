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
