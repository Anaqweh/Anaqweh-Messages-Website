def _can_access_registrations(request):
    try:
        from apps.registrations.form_permissions import request_allowed_by_path
        return request_allowed_by_path(request)
    except Exception:
        pass

    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return False

    if getattr(user, "is_superuser", False):
        return True

    try:
        from apps.platform_core.navigation import active_membership_for
        membership = active_membership_for(user)
        if not membership:
            return False

        modules = getattr(membership.tenant, "modules", None) or {}
        perms = getattr(membership, "permissions", None) or {}
        reg = perms.get("registrations", {})

        return bool(
            getattr(membership, "is_tenant_admin", False)
            or modules.get("registrations")
            or reg.get("view")
            or reg.get("create")
            or reg.get("settings")
        )
    except Exception:
        return False


class RegistrationAccessOverrideMiddleware:
    """
    يسمح لمدير الشركة بفتح نموذج سبارك إذا كانت صلاحية التسجيل مفعلة.
    لا يلمس قالب OCR ولا الكاميرا.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not request.path.startswith("/registrations/templates/"):
            return response

        if "/spark-fill/" not in request.path:
            return response

        if not _can_access_registrations(request):
            return response

        if response.status_code not in (301, 302, 303, 307, 308, 403):
            return response

        try:
            from django.urls import resolve
            match = resolve(request.path)
            return match.func(request, *match.args, **match.kwargs)
        except Exception:
            return response
