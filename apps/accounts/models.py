from django.conf import settings

from apps.accounts.audit import AuditLog, log_action

from django.db import models
from django.contrib.auth.models import User

class UserEmailJSConfig(models.Model):
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='emailjs_config')
    service_id     = models.CharField(max_length=100, blank=True)
    template_id    = models.CharField(max_length=100, blank=True)
    public_key     = models.CharField(max_length=100, blank=True)
    private_key    = models.CharField(max_length=100, blank=True)
    from_email     = models.EmailField(blank=True, help_text='البريد الذي سيظهر كمرسل')
    from_name      = models.CharField(max_length=100, blank=True, help_text='الاسم الذي سيظهر كمرسل')
    is_configured  = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'إعدادات EmailJS'
        verbose_name_plural = 'إعدادات EmailJS للمستخدمين'

    def __str__(self):
        return f'EmailJS config for {self.user.username}'


class UserProfile(models.Model):
    user      = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    note      = models.TextField(blank=True, help_text='ملاحظة عن المستخدم')
    max_sends = models.IntegerField(default=0, help_text='الحد الأقصى للإرسال (0 = بلا حد)')
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ملف المستخدم'
        verbose_name_plural = 'ملفات المستخدمين'

    def __str__(self):
        return f'Profile: {self.user.username}'


class PasswordResetCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def is_valid(self):
        from django.utils import timezone
        from datetime import timedelta
        return not self.is_used and self.created_at >= timezone.now() - timedelta(minutes=15)
