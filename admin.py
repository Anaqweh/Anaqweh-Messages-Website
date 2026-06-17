from django.contrib import admin
from .models import EmailTemplate

@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display  = ['name', 'subject', 'is_active', 'created_at']
    list_filter   = ['is_active']
    search_fields = ['name', 'subject']
