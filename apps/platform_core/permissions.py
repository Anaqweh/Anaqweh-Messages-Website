from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import TenantMembership, default_permissions


def get_active_membership(user, tenant=None):
    if not user or not user.is_authenticated:
        return None

    qs = TenantMembership.objects.filter(user=user)
    if tenant is not None:
        qs = qs.filter(tenant=tenant)

    if any(field.name == "is_active" for field in TenantMembership._meta.fields):
        qs = qs.filter(is_active=True)

    return qs.select_related("tenant").first()


def permissions_for_membership(membership):
    permissions = default_permissions()

    if not membership:
        return permissions

    role = getattr(membership, "role", None)
    role_permissions = getattr(role, "permissions", None)
    if role_permissions:
        permissions.update(role_permissions)

    member_permissions = getattr(membership, "permissions", None)
    if member_permissions:
        permissions.update(member_permissions)

    return permissions


def has_permission(user, section, action, tenant=None):
    if user and (user.is_superuser or user.is_staff):
        return True

    membership = get_active_membership(user, tenant=tenant)
    permissions = permissions_for_membership(membership)

    return bool(permissions.get(section, {}).get(action))


def tenant_permission_required(section, action):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if has_permission(request.user, section, action):
                return view_func(request, *args, **kwargs)

            messages.error(request, "ليست لديك صلاحية لتنفيذ هذا الإجراء.")
            return redirect("workspace:home")
        return wrapped
    return decorator
