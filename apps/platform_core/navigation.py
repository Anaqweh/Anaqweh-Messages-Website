from django.urls import reverse

from .models import TenantMembership, default_permissions


def is_platform_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def active_membership_for(user):
    if not user or not user.is_authenticated:
        return None

    qs = TenantMembership.objects.select_related("tenant", "role").filter(user=user)

    if any(field.name == "is_active" for field in TenantMembership._meta.fields):
        qs = qs.filter(is_active=True)

    return qs.order_by("-id").first()


def _deep_merge_permissions(base, override):
    if not override:
        return base

    for section, actions in override.items():
        base.setdefault(section, {})
        if isinstance(actions, dict):
            for action, value in actions.items():
                base[section][action] = bool(value)
    return base


def _inexc_original_permissions_for_membership(membership):
    permissions = default_permissions()

    if not membership:
        return permissions

    role = getattr(membership, "role", None)
    role_permissions = getattr(role, "permissions", None)
    permissions = _deep_merge_permissions(permissions, role_permissions)

    member_permissions = getattr(membership, "permissions", None)
    permissions = _deep_merge_permissions(permissions, member_permissions)

    return permissions


def has_tenant_permission(user, section, action):
    if is_platform_admin(user):
        return True

    membership = active_membership_for(user)
    permissions = permissions_for_membership(membership)

    return bool(permissions.get(section, {}).get(action, False))


def dashboard_url_for_user(user):
    if not user or not user.is_authenticated:
        return reverse("accounts:login")

    if is_platform_admin(user):
        return reverse("platform_core:tenant_list")

    if active_membership_for(user):
        return reverse("workspace:home")

    return reverse("campaigns:dashboard")


# INEXC_ACCOUNTING_PERMISSION_PATCH
def _inexc_original_permissions_for_membership(membership):
    perms = _inexc_original_permissions_for_membership(membership) or {}

    if not membership:
        return perms

    modules = getattr(getattr(membership, "tenant", None), "modules", None) or {}
    if modules.get("accounting", False) and "accounting" not in perms:
        finance = perms.get("finance", {})
        can_view = bool(finance.get("view")) or bool(getattr(membership, "is_tenant_admin", False))
        perms["accounting"] = {
            "view": can_view,
            "create": bool(finance.get("create", can_view)),
            "edit": bool(finance.get("edit", can_view)),
            "delete": bool(finance.get("delete", False)),
            "export": bool(finance.get("export", can_view)),
            "payroll": can_view,
        }

    return perms


# INEXC_FORCE_ACCOUNTING_PERMISSION_FINAL
def permissions_for_membership(membership):
    perms = _inexc_original_permissions_for_membership(membership) or {}

    if not membership:
        return perms

    modules = getattr(getattr(membership, "tenant", None), "modules", None) or {}

    if modules.get("accounting", False):
        finance = perms.get("finance", {})
        old = perms.get("accounting", {})
        can_view = bool(old.get("view")) or bool(finance.get("view")) or bool(getattr(membership, "is_tenant_admin", False))

        perms["accounting"] = {
            "view": can_view,
            "create": bool(old.get("create")) or bool(finance.get("create", can_view)),
            "edit": bool(old.get("edit")) or bool(finance.get("edit", can_view)),
            "delete": bool(old.get("delete")) or bool(finance.get("delete", False)),
            "export": bool(old.get("export")) or bool(finance.get("export", can_view)),
            "payroll": bool(old.get("payroll")) or can_view,
        }

    return perms


# INEXC_PERMISSIONS_FINAL_NO_RECURSION
def permissions_for_membership(membership):
    """
    نسخة نهائية آمنة: لا تستدعي أي نسخة قديمة حتى لا يحدث recursion.
    تحفظ الصلاحيات اليدوية، وتضيف accounting فقط إذا كانت الوحدة مفعلة ولم تكن موجودة.
    """
    import copy

    if not membership:
        return {}

    raw = getattr(membership, "permissions", None) or {}
    perms = copy.deepcopy(raw) if isinstance(raw, dict) else {}

    tenant = getattr(membership, "tenant", None)
    modules = getattr(tenant, "modules", None) or {}
    is_tenant_admin = bool(getattr(membership, "is_tenant_admin", False))

    finance = perms.get("finance", {})
    if not isinstance(finance, dict):
        finance = {}

    if modules.get("accounting", False):
        accounting_existed = isinstance(perms.get("accounting"), dict)
        accounting = perms.get("accounting") if accounting_existed else {}

        can_view = bool(finance.get("view")) or is_tenant_admin

        defaults = {
            "view": can_view,
            "create": bool(finance.get("create", can_view)),
            "edit": bool(finance.get("edit", can_view)),
            "delete": bool(finance.get("delete", False)),
            "export": bool(finance.get("export", can_view)),
            "payroll": can_view,
        }

        for key, value in defaults.items():
            accounting.setdefault(key, value)

        perms["accounting"] = accounting

    return perms
