from django.contrib import admin

from .models import ModuleCatalog, PlatformAuditLog, Tenant, TenantMembership, TenantRole


@admin.register(ModuleCatalog)
class ModuleCatalogAdmin(admin.ModelAdmin):
    list_display = ("code", "name_ar", "name_en", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("code", "name_ar", "name_en")
    ordering = ("sort_order", "code")


class TenantRoleInline(admin.TabularInline):
    model = TenantRole
    extra = 0


class TenantMembershipInline(admin.TabularInline):
    model = TenantMembership
    extra = 0
    autocomplete_fields = ("user", "role")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "plan_name", "owner_email", "subscription_ends_at", "updated_at")
    list_filter = ("status", "plan_name")
    search_fields = ("name", "slug", "owner_name", "owner_email", "domain")
    inlines = [TenantRoleInline, TenantMembershipInline]


@admin.register(TenantRole)
class TenantRoleAdmin(admin.ModelAdmin):
    list_display = ("tenant", "name", "is_active", "is_system", "updated_at")
    list_filter = ("is_active", "is_system", "tenant")
    search_fields = ("tenant__name", "name")
    autocomplete_fields = ("tenant",)


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("tenant", "user", "role_name", "role", "is_tenant_admin", "is_active", "updated_at")
    list_filter = ("is_tenant_admin", "is_active", "tenant")
    search_fields = ("tenant__name", "user__username", "user__email", "role_name")
    autocomplete_fields = ("tenant", "user", "role")


@admin.register(PlatformAuditLog)
class PlatformAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "tenant", "action", "target_model", "target_id")
    list_filter = ("action", "tenant")
    search_fields = ("action", "target_model", "target_id", "actor__username", "tenant__name")
    readonly_fields = ("created_at",)


# تعريب أسماء النماذج (عرض فقط)
from .models import ModuleCatalog, Tenant, TenantRole, TenantMembership, PlatformAuditLog
for _m, (_s, _p) in {
    ModuleCatalog: ("وحدة", "كتالوج الوحدات"),
    Tenant: ("شركة", "الشركات"),
    TenantRole: ("دور", "أدوار الشركات"),
    TenantMembership: ("عضوية", "عضويات الشركات"),
    PlatformAuditLog: ("سجل تدقيق", "سجلات التدقيق"),
}.items():
    _m._meta.verbose_name = _s
    _m._meta.verbose_name_plural = _p


# تصحيح تعريب (عرض فقط)
try:
    from .models import PlatformSettings, PayoutRequest
    PlatformSettings._meta.verbose_name = "إعدادات المنصة"
    PlatformSettings._meta.verbose_name_plural = "إعدادات المنصة"
    PayoutRequest._meta.verbose_name = "طلب سحب"
    PayoutRequest._meta.verbose_name_plural = "طلبات السحب"
except Exception:
    pass
