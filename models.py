from django.db import models


class EmailTemplate(models.Model):
    name       = models.CharField(max_length=200, verbose_name='اسم القالب')
    subject    = models.CharField(max_length=500, verbose_name='عنوان الرسالة')
    body_html  = models.TextField(verbose_name='محتوى HTML')
    body_text  = models.TextField(blank=True, verbose_name='محتوى نصي')
    is_active  = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Supported variables hint
    SUPPORTED_VARS = ['{{name}}', '{{email}}', '{{phone}}',
                      '{{course_name}}', '{{custom_message}}']

    class Meta:
        verbose_name = 'قالب بريدي'
        verbose_name_plural = 'القوالب البريدية'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def render(self, context: dict) -> tuple[str, str]:
        """Render subject and body with context variables."""
        subject = self.subject
        html    = self.body_html
        text    = self.body_text

        for key, value in context.items():
            placeholder = '{{' + key + '}}'
            subject = subject.replace(placeholder, str(value or ''))
            html    = html.replace(placeholder, str(value or ''))
            text    = text.replace(placeholder, str(value or ''))

        return subject, html, text
