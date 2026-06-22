from django.contrib import admin

from .models import CRMCompany, CRMContact, CRMDeal, CRMTask


@admin.register(CRMCompany)
class CRMCompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "email", "phone", "tenant", "owner", "updated_at")
    list_filter = ("status", "tenant")
    search_fields = ("name", "email", "phone", "trn")


@admin.register(CRMContact)
class CRMContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company", "email", "phone", "tenant", "owner", "updated_at")
    list_filter = ("tenant",)
    search_fields = ("full_name", "email", "phone", "company__name")


@admin.register(CRMDeal)
class CRMDealAdmin(admin.ModelAdmin):
    list_display = ("title", "stage", "value", "currency", "company", "owner", "updated_at")
    list_filter = ("stage", "tenant")
    search_fields = ("title", "company__name", "contact__full_name")


@admin.register(CRMTask)
class CRMTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "priority", "task_type", "due_at", "assigned_to", "tenant")
    list_filter = ("status", "priority", "task_type", "tenant")
    search_fields = ("title", "notes")
