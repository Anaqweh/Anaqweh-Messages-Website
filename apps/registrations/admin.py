from django.contrib import admin


# تعريب (عرض فقط)
try:
    from .models import RegistrationFormTemplate, RegistrationSubmission
    RegistrationFormTemplate._meta.verbose_name = "نموذج تسجيل"
    RegistrationFormTemplate._meta.verbose_name_plural = "نماذج التسجيل"
    RegistrationSubmission._meta.verbose_name = "طلب تسجيل"
    RegistrationSubmission._meta.verbose_name_plural = "طلبات التسجيل"
except Exception:
    pass
