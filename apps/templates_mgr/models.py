from django.db import models

class EmailTemplate(models.Model):
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True, related_name='templates')
    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=500)
    body_html = models.TextField()
    body_text = models.TextField(blank=True)
    blocks_json = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    SUPPORTED_VARS = ['{{name}}','{{email}}','{{phone}}','{{course_name}}','{{custom_message}}']
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return self.name
    def render(self, context):
        subject = self.subject
        html = self.body_html
        text = self.body_text
        for key, value in context.items():
            p = '{{' + key + '}}'
            subject = subject.replace(p, str(value or ''))
            html = html.replace(p, str(value or ''))
            text = text.replace(p, str(value or ''))
        return subject, html, text


import uuid as _uuid


class BankPaymentPage(models.Model):
    """صفحة معلومات دفع/تحويل بنكي لها رابط قصير"""
    code = models.CharField(max_length=12, unique=True, db_index=True)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True, related_name='bank_pages')
    title = models.CharField(max_length=200, default='معلومات الدفع')
    bank_name = models.CharField(max_length=200, blank=True)
    account_name = models.CharField(max_length=200, blank=True)
    iban = models.CharField(max_length=80, blank=True)
    account_number = models.CharField(max_length=80, blank=True)
    swift = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=80, blank=True)
    currency = models.CharField(max_length=20, blank=True)
    amount = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = _uuid.uuid4().hex[:10]
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} ({self.code})'
