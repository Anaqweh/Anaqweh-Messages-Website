import threading

from .navigation import active_membership_for, is_platform_admin

_state = threading.local()


def set_current_tenant(tenant):
    _state.tenant = tenant


def get_current_tenant():
    return getattr(_state, "tenant", None)


class TenantContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_tenant(None)

        user = getattr(request, "user", None)
        if user and user.is_authenticated and not is_platform_admin(user):
            membership = active_membership_for(user)
            if membership:
                set_current_tenant(membership.tenant)

        try:
            return self.get_response(request)
        finally:
            set_current_tenant(None)
