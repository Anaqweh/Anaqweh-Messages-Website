from django.db import models
from django.utils import timezone
from apps.recipients.models import MailingList, Recipient
from apps.templates_mgr.models import EmailTemplate

class Campaign(models.Model):
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, blank=True, related_name='campaigns')
    STATUS_CHOICES = [('draft','مسودة'),('scheduled','مجدولة'),('running','جارية'),('paused','متوقفة'),('completed','مكتملة'),('cancelled','ملغاة')]
    name = models.CharField(max_length=300)
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    mailing_list = models.ForeignKey(MailingList, on_delete=models.SET_NULL, null=True, related_name='campaigns')
    subject = models.CharField(max_length=500)
    body_html = models.TextField()
    body_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=200, blank=True)
    recurrence = models.CharField(max_length=20, default='none', choices=[('none','بدون تكرار'),('daily','يومي'),('weekly','أسبوعي'),('monthly','شهري')])
    next_run = models.DateTimeField(null=True, blank=True)
    is_recurring_active = models.BooleanField(default=False)
    ab_test_enabled = models.BooleanField(default=False)
    subject_b = models.CharField(max_length=500, blank=True)
    body_html_b = models.TextField(blank=True)
    ab_split_percent = models.IntegerField(default=50)
    ab_variant = models.CharField(max_length=1, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return self.name
    @property
    def total_recipients(self):
        return self.logs.count()
    @property
    def sent_count(self):
        return self.logs.filter(status='sent').count()
    @property
    def failed_count(self):
        return self.logs.filter(status='failed').count()
    @property
    def pending_count(self):
        return self.logs.filter(status__in=['pending','sending']).count()
    @property
    def success_rate(self):
        t = self.total_recipients
        return round((self.sent_count/t)*100,1) if t>0 else 0
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    def get_status_color(self):
        return {'draft':'secondary','scheduled':'info','running':'primary','paused':'warning','completed':'success','cancelled':'danger'}.get(self.status,'secondary')


class CampaignMessageStep(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='message_steps')
    step_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=500)
    body_html = models.TextField()
    body_text = models.TextField(blank=True)
    send_at = models.DateTimeField(null=True, blank=True)
    delay_minutes = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['campaign', 'step_number']
        unique_together = [('campaign', 'step_number')]

    def __str__(self):
        return f'{self.campaign.name} - message {self.step_number}'

class EmailLog(models.Model):
    STATUS_CHOICES = [('pending','قيد الانتظار'),('sending','جارٍ'),('sent','تم'),('failed','فشل'),('bounced','مرتد'),('opened','فُتح'),('clicked','نُقر')]
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='logs')
    recipient = models.ForeignKey(Recipient, on_delete=models.SET_NULL, null=True, related_name='logs')
    recipient_name = models.CharField(max_length=200, blank=True)
    recipient_email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    attempts = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    message_id = models.CharField(max_length=500, blank=True)
    message_step = models.ForeignKey('CampaignMessageStep', on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    subject_snapshot = models.CharField(max_length=500, blank=True)
    body_html_snapshot = models.TextField(blank=True)
    body_text_snapshot = models.TextField(blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    open_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    emailjs_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f'{self.recipient_email} - {self.status}'
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    def get_status_color(self):
        return {'pending':'warning','sending':'info','sent':'success','failed':'danger','bounced':'secondary','opened':'primary','clicked':'purple'}.get(self.status,'secondary')

class SmartSendBatch(models.Model):
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='smart_batches')
    subject = models.CharField(max_length=300, blank=True)
    body_html = models.TextField(blank=True)
    total = models.IntegerField(default=0)
    success = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='running')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    delay = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'دفعة إرسال ذكي'


class SmartSendRecipientLog(models.Model):
    batch = models.ForeignKey(SmartSendBatch, on_delete=models.CASCADE, related_name='logs')
    email = models.CharField(max_length=254)
    name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, default='pending')
    error = models.CharField(max_length=200, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    open_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('batch', 'email')
