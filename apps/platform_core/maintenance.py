"""وضع الصيانة الأنيق — يُفعَّل بوجود ملف maintenance_on في جذر المشروع."""
import os
from django.shortcuts import render


class MaintenanceMiddleware:
    FLAG = "/app/maintenance_on"
    ALLOW_PREFIX = ("/healthz", "/accounts/login", "/static", "/media", "/admin")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if os.path.exists(self.FLAG):
            u = getattr(request, "user", None)
            if not (u and u.is_authenticated and u.is_superuser):
                if not request.path.startswith(self.ALLOW_PREFIX):
                    resp = render(request, "maintenance.html", status=503)
                    resp["Retry-After"] = "120"
                    return resp
        return self.get_response(request)
