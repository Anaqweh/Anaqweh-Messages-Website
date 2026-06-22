from .navigation import active_membership_for, is_platform_admin, permissions_for_membership


def _permissions_from_modules(modules):
    """يبني صلاحيات القائمة من وحدات الشركة."""
    return {
        'email': {
            'view': modules.get('email', False),
            'create': modules.get('email', False),
            'edit': modules.get('email', False),
            'delete': modules.get('email', False),
            'send': modules.get('email', False),
        },
        'finance': {
            'view': modules.get('finance', False),
            'create': modules.get('finance', False),
            'edit': modules.get('finance', False),
            'delete': modules.get('finance', False),
            'export': modules.get('finance', False),
        },
        'crm': {
            'view': modules.get('crm', False),
            'create': modules.get('crm', False),
            'edit': modules.get('crm', False),
            'delete': modules.get('crm', False),
            'export': modules.get('crm', False),
        },
        'reports': {
            'view': modules.get('reports', False),
            'export': modules.get('reports', False),
        },
        'settings': {
            'view': True,
            'edit': True,
            'manage_users': True,
        },
    }


def tenant_permissions(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'tenant_membership': None, 'tenant_permissions': {}, 'active_tenant_context': None}

    # المدير العام
    if is_platform_admin(user):
        active_tenant_id = request.session.get('active_tenant_id')
        active_tenant_name = request.session.get('active_tenant_name', '')
        if active_tenant_id:
            try:
                from .models import Tenant
                tenant = Tenant.objects.get(pk=active_tenant_id)
                # نقرأ صلاحيات الشركة الفعلية من modules
                perms = _permissions_from_modules(tenant.modules or {})
                return {
                    'tenant_membership': None,
                    'tenant_permissions': perms,
                    'active_tenant_context': {
                        'id': active_tenant_id,
                        'name': active_tenant_name,
                        'modules': tenant.modules,
                    },
                }
            except Exception:
                request.session.pop('active_tenant_id', None)
                request.session.pop('active_tenant_name', None)
        # المدير العام بدون شركة مختارة
        return {
            'tenant_membership': None,
            'tenant_permissions': {},
            'active_tenant_context': None,
        }

    # مستخدم عادي
    membership = active_membership_for(user)
    return {
        'tenant_membership': membership,
        'tenant_permissions': permissions_for_membership(membership) if membership else {},
        'active_tenant_context': None,
    }
