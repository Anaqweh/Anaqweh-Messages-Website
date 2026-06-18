from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    ip_address = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'سجل نشاط'

    def __str__(self):
        return f'{self.username} - {self.action}'

def log_action(request, action, details=''):
    """Helper to record an audit entry."""
    try:
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            username=request.user.username if request.user.is_authenticated else 'مجهول',
            action=action, details=details, ip_address=ip,
        )
    except Exception:
        pass
