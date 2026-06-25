from django.shortcuts import redirect

from .navigation import active_membership_for, is_platform_admin, permissions_for_membership


class TenantPermissionMiddleware:
    PUBLIC_PREFIXES = (
        "/accounts/login/",
        "/accounts/logout/",
        "/static/",
        "/media/",
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





    PLATFORM_ONLY_PREFIXES = (
        "/platform/",
        "/django-admin/",
        "/accounts/users/",
        "/accounts/audit-log/",
        "/accounts/emailjs-settings/",
        "/accounts/emailjs-test/",
        "/payments/payouts/",
        "/accounting/",
    )

    MODULE_PREFIXES = (
        ("/crm/", "crm"),
        ("/payments/", "finance"),
        ("/campaigns/", "email"),
        ("/templates/", "email"),
        ("/recipients/", "email"),
        ("/reports/", "reports"),
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info or request.path
        user = getattr(request, "user", None)

        if path.startswith(self.PUBLIC_PREFIXES):
            return self.get_response(request)

        if not user or not user.is_authenticated:
            return self.get_response(request)

        if is_platform_admin(user):
            return self.get_response(request)

        membership = active_membership_for(user)
        permissions = permissions_for_membership(membership)

        if path.startswith(self.PLATFORM_ONLY_PREFIXES):
            return redirect("workspace:home")

        for prefix, section in self.MODULE_PREFIXES:
            if path.startswith(prefix):
                action = self._action_for_path(path)
                if not permissions.get(section, {}).get(action, False):
                    return redirect("workspace:access_denied")
                break

        return self.get_response(request)

    def _action_for_path(self, path):
        if "/delete/" in path:
            return "delete"
        if "/edit/" in path:
            return "edit"
        if path.endswith("/new/") or "/new/" in path or "/create/" in path:
            return "create"
        if "/send/" in path or "test-send" in path or "do-send" in path:
            return "send"
        if "/pdf/" in path or "export" in path:
            return "export"
        return "view"
