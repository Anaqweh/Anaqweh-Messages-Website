from django.db import models
from django.utils import timezone

class MailingList(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = 'قائمة بريدية'
    def __str__(self):
        return self.name
    @property
    def active_count(self):
        return self.recipients.filter(is_active=True, is_unsubscribed=False).count()

class Recipient(models.Model):
    mailing_list = models.ForeignKey(MailingList, on_delete=models.CASCADE, related_name='recipients')
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    custom_field_1 = models.CharField(max_length=500, blank=True)
    custom_field_2 = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    is_unsubscribed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ('mailing_list', 'email')
    def __str__(self):
        return self.email

class UnsubscribeList(models.Model):
    email = models.EmailField(unique=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.email

class UploadBatch(models.Model):
    STATUS_CHOICES = [('pending','قيد المعالجة'),('processing','جارٍ'),('done','مكتمل'),('failed','فشل')]
    mailing_list = models.ForeignKey(MailingList, on_delete=models.CASCADE, related_name='upload_batches')
    file = models.FileField(upload_to='uploads/')
    original_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_rows = models.IntegerField(default=0)
    imported = models.IntegerField(default=0)
    duplicates = models.IntegerField(default=0)
    invalid = models.IntegerField(default=0)
    error_report = models.JSONField(default=list)
    email_column = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    def __str__(self):
        return self.original_name
