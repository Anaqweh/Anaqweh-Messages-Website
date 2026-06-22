from django.db import models
from django.conf import settings
from django.utils import timezone


class TaskWorkflowTemplate(models.Model):
    """قالب سير العمل — مثل: تصميم إعلان، إعداد شهادة..."""
    tenant = models.ForeignKey('platform_core.Tenant', null=True, blank=True, on_delete=models.SET_NULL, related_name='workflow_templates')
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TaskWorkflowStage(models.Model):
    """مرحلة في قالب سير العمل"""
    template = models.ForeignKey(TaskWorkflowTemplate, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    role_required = models.CharField(max_length=120, blank=True, help_text='الدور المطلوب لهذه المرحلة')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.template.name} → {self.name}'


class Task(models.Model):
    STATUS_CHOICES = [
        ('new', 'جديدة'),
        ('in_progress', 'قيد التنفيذ'),
        ('pending_review', 'بانتظار المراجعة'),
        ('returned', 'معادة للتعديل'),
        ('late', 'متأخرة'),
        ('on_hold', 'معلقة'),
        ('completed', 'مكتملة'),
        ('cancelled', 'ملغاة'),
        ('published', 'منشورة'),
    ]
    PRIORITY_CHOICES = [
        ('urgent', 'عاجلة'),
        ('high', 'عالية'),
        ('medium', 'متوسطة'),
        ('low', 'منخفضة'),
    ]

    tenant = models.ForeignKey('platform_core.Tenant', null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=120, blank=True, help_text='نوع المهمة: تصميم إعلان، كتابة منشور...')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='new')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    # سير العمل
    workflow_template = models.ForeignKey(TaskWorkflowTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    current_stage = models.ForeignKey(TaskWorkflowStage, null=True, blank=True, on_delete=models.SET_NULL, related_name='current_tasks')

    # الأشخاص
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_tasks')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_tasks')

    # ربط اختياري بـ CRM
    crm_company = models.ForeignKey('crm.CRMCompany', null=True, blank=True, on_delete=models.SET_NULL, related_name='workflow_tasks')
    crm_deal = models.ForeignKey('crm.CRMDeal', null=True, blank=True, on_delete=models.SET_NULL, related_name='workflow_tasks')

    # التواريخ
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # إضافية
    notes = models.TextField(blank=True)
    external_links = models.TextField(blank=True, help_text='روابط خارجية، كل رابط في سطر')
    return_reason = models.TextField(blank=True, help_text='سبب الإرجاع للتعديل')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_late(self):
        if self.due_date and self.status not in ('completed', 'cancelled', 'published'):
            return self.due_date < timezone.now().date()
        return False

    def save(self, *args, **kwargs):
        if self.is_late and self.status not in ('completed', 'cancelled', 'published', 'late'):
            self.status = 'late'
        super().save(*args, **kwargs)


class TaskStageLog(models.Model):
    """سجل انتقال المهمة بين المراحل"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='stage_logs')
    from_stage = models.ForeignKey(TaskWorkflowStage, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    to_stage = models.ForeignKey(TaskWorkflowStage, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    action = models.CharField(max_length=120)
    notes = models.TextField(blank=True)
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.task} → {self.action}'


class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'تعليق على {self.task}'


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    file = models.FileField(upload_to='tasks/attachments/%Y/%m/')
    name = models.CharField(max_length=220, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.file.name
