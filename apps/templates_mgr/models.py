from django.db import models

class EmailTemplate(models.Model):
    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=500)
    body_html = models.TextField()
    body_text = models.TextField(blank=True)
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
