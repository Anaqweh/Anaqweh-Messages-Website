def crm_tenant_for_request(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return None

    # المدير العام له مساحة عامة منفصلة: tenant = NULL
    if getattr(user, "is_superuser", False):
        return None

    try:
        from apps.platform_core.navigation import active_membership_for
        membership = active_membership_for(user)
        return membership.tenant if membership else None
    except Exception:
        return None


def crm_scope_queryset(request, model):
    qs = model.objects.all()
    field_names = {f.name for f in model._meta.fields}

    if "tenant" not in field_names:
        return qs

    tenant = crm_tenant_for_request(request)

    if tenant is None:
        if getattr(getattr(request, "user", None), "is_superuser", False):
            return qs.filter(tenant__isnull=True)
        return qs.none()

    return qs.filter(tenant=tenant)


def assign_crm_tenant(request, obj):
    field_names = {f.name for f in obj._meta.fields}

    if "tenant" in field_names:
        obj.tenant = crm_tenant_for_request(request)

    if "owner" in field_names and not getattr(obj, "owner_id", None):
        obj.owner = request.user

    return obj

# INEXC_FINAL_CRM_QUOTE_CONTEXT
def apply_crm_admin_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return False

    value = request.GET.get("tenant_context")
    if value is None:
        return False

    if value in ("", "platform", "admin", "none"):
        request.session.pop("active_tenant_id", None)
        request.session.pop("active_tenant_name", None)
        return True

    try:
        from apps.platform_core.models import Tenant
        tenant = Tenant.objects.get(pk=int(value))
        request.session["active_tenant_id"] = tenant.id
        request.session["active_tenant_name"] = tenant.name
        return True
    except Exception:
        return False


def selected_crm_admin_tenant(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return None

    tenant_id = request.session.get("active_tenant_id")
    if not tenant_id:
        return None

    try:
        from apps.platform_core.models import Tenant
        return Tenant.objects.get(pk=tenant_id)
    except Exception:
        request.session.pop("active_tenant_id", None)
        request.session.pop("active_tenant_name", None)
        return None


def crm_tenant_for_request(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return None

    if user.is_superuser:
        return selected_crm_admin_tenant(request)

    try:
        from apps.platform_core.navigation import active_membership_for
        membership = active_membership_for(user)
        return membership.tenant if membership else None
    except Exception:
        return None


def crm_scope_queryset(request, model):
    qs = model.objects.all()
    field_names = {f.name for f in model._meta.fields}

    if "tenant" not in field_names:
        return qs

    tenant = crm_tenant_for_request(request)
    user = getattr(request, "user", None)

    if tenant is None:
        if user and user.is_superuser:
            return qs.filter(tenant__isnull=True)
        return qs.none()

    return qs.filter(tenant=tenant)


def assign_crm_tenant(request, obj):
    field_names = {f.name for f in obj._meta.fields}

    if "tenant" in field_names:
        obj.tenant = crm_tenant_for_request(request)

    if "owner" in field_names and not getattr(obj, "owner_id", None):
        obj.owner = request.user

    return obj


def quote_context_data(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return {
            "is_platform_admin_quote": False,
            "quote_tenants": [],
            "selected_quote_tenant_id": "",
            "selected_quote_context_label": "",
        }

    try:
        from apps.platform_core.models import Tenant
        tenants = Tenant.objects.order_by("name")
    except Exception:
        tenants = []

    selected = selected_crm_admin_tenant(request)
    return {
        "is_platform_admin_quote": True,
        "quote_tenants": tenants,
        "selected_quote_tenant_id": str(selected.id) if selected else "platform",
        "selected_quote_context_label": selected.name if selected else "المدير العام",
    }
