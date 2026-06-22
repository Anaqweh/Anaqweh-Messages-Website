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


def permissions_for_membership(membership):
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
