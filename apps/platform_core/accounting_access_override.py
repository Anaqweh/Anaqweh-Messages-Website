from django.shortcuts import redirect


def _can_access_accounting(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return False

    if getattr(user, "is_superuser", False):
        return True

    try:
        from apps.platform_core.navigation import active_membership_for, permissions_for_membership

        membership = active_membership_for(user)
        if not membership:
            return False

        modules = getattr(membership.tenant, "modules", None) or {}
        perms = permissions_for_membership(membership) or {}

        finance = perms.get("finance", {})
        accounting = perms.get("accounting", {})

        return bool(
            getattr(membership, "is_tenant_admin", False)
            or modules.get("accounting")
            or accounting.get("view")
            or accounting.get("payroll")
            or finance.get("view")
        )
    except Exception:
        return False


class AccountingAccessOverrideMiddleware:
    """
    يمنع التحويل الخاطئ من صفحات المحاسبة إلى /workspace/
    عندما يكون مدير الشركة لديه صلاحية مالية/محاسبة.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not request.path.startswith("/accounting/"):
            return response

        if not _can_access_accounting(request):
            return response

        location = response.get("Location", "")
        if response.status_code not in (301, 302, 303, 307, 308):
            return response

        if not location.startswith("/workspace"):
            return response

        # أهم صفحة حالياً: الموظفون والرواتب
        if request.path.rstrip("/") == "/accounting/employees":
            from apps.accounting.tenant_access_views import employees
            return employees(request)

        # لأي صفحة محاسبة أخرى: حاول فتح الـ view الحقيقي بدل التحويل
        try:
            from django.urls import resolve
            match = resolve(request.path)
            return match.func(request, *match.args, **match.kwargs)
        except Exception:
            return response
