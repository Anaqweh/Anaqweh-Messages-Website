from django.contrib import admin


# تعريب (عرض فقط)
try:
    from .models import AuditLog, UserEmailJSConfig, PasswordResetCode
    AuditLog._meta.verbose_name = "سجل نشاط"
    AuditLog._meta.verbose_name_plural = "سجلات النشاط"
    UserEmailJSConfig._meta.verbose_name = "إعداد EmailJS"
    UserEmailJSConfig._meta.verbose_name_plural = "إعدادات EmailJS"
    PasswordResetCode._meta.verbose_name = "رمز استعادة"
    PasswordResetCode._meta.verbose_name_plural = "رموز الاستعادة"
except Exception:
    pass
