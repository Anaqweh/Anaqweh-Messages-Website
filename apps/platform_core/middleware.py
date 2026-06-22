from django.shortcuts import redirect
from django.urls import reverse


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
