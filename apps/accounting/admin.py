from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'email', 'phone', 'is_active', 'created_at')
    search_fields = ('name', 'email', 'phone', 'company')
    list_filter = ('is_active',)
