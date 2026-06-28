from django.shortcuts import redirect
from django.urls import reverse



# INEXC_ALLOW_ACCOUNTING_ACCESS_PATCH
def _inexc_user_can_access_accounting(request):
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

        accounting = perms.get("accounting", {})
        finance = perms.get("finance", {})

        return bool(
            modules.get("accounting")
            or accounting.get("view")
            or accounting.get("payroll")
            or finance.get("view")
            or getattr(membership, "is_tenant_admin", False)
        )
    except Exception:
        return False


class FinanceAccessIsolationMiddleware:
    PUBLIC_PAYMENT_PREFIXES = (
        "/payments/invoice/",
        "/payments/sales-invoice/",
        "/payments/stripe/webhook/",
        "/payments/checkout/",
        "/payments/create-checkout/",
        "/payments/quick-checkout/",
        "/payments/pay-success/",
        "/payments/pay-cancel/",
        "/payments/success/",
        "/payments/cancel/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/accounting/") and _inexc_user_can_access_accounting(request):
            return self.get_response(request)

        path = request.path_info or request.path
        if not path.startswith("/payments/"):
            return self.get_response(request)
        if path.startswith(self.PUBLIC_PAYMENT_PREFIXES):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            login_url = reverse("accounts:login")
            return redirect(f"{login_url}?next={path}")

        # المدير العام — سواء بسياق شركة أو بدونه، يمر مباشرة
        if user.is_superuser or user.is_staff:
            return self.get_response(request)

        # مستخدم شركة — نتحقق من صلاحية finance.view
        try:
            from .navigation import active_membership_for, permissions_for_membership
            membership = active_membership_for(user)
            if membership:
                perms = permissions_for_membership(membership)
                if perms.get('finance', {}).get('view', False):
                    return self.get_response(request)
        except Exception:
            pass

        return redirect("workspace:finance")
