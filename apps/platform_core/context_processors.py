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
        'accounting': {
            'view': modules.get('accounting', modules.get('finance', False)),
            'create': modules.get('accounting', modules.get('finance', False)),
            'edit': modules.get('accounting', modules.get('finance', False)),
            'delete': modules.get('accounting', modules.get('finance', False)),
            'export': modules.get('accounting', modules.get('finance', False)),
            'payroll': modules.get('accounting', modules.get('finance', False)),
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
        'registrations': {
            'view': modules.get('registrations', False),
            'create': modules.get('registrations', False),
            'edit': modules.get('registrations', False),
            'delete': modules.get('registrations', False),
            'settings': modules.get('registrations', False),
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
                reg_perms = perms.get('registrations', {})
                return {
                    'tenant_membership': None,
                    'tenant_permissions': perms,
                    'tenant_modules': tenant.modules or {},
                    'active_tenant_context': {
                        'id': active_tenant_id,
                        'name': active_tenant_name,
                        'modules': tenant.modules,
                    },
                    'perms_registrations_view': reg_perms.get('view', False),
                    'perms_registrations_create': reg_perms.get('create', False),
                    'perms_registrations_edit': reg_perms.get('edit', False),
                    'perms_registrations_delete': reg_perms.get('delete', False),
                    'perms_registrations_settings': reg_perms.get('settings', False),
                }
            except Exception:
                request.session.pop('active_tenant_id', None)
                request.session.pop('active_tenant_name', None)
        # المدير العام بدون شركة مختارة - نعطيه modules من أول شركة
        try:
            from .models import Tenant
            first_tenant = Tenant.objects.first()
            admin_modules = first_tenant.modules if first_tenant else {}
        except Exception:
            admin_modules = {}
        admin_reg = admin_modules.get('registrations', False)
        return {
            'tenant_membership': None,
            'tenant_permissions': {},
            'tenant_modules': admin_modules,
            'active_tenant_context': None,
            'perms_registrations_view': admin_reg,
            'perms_registrations_create': admin_reg,
            'perms_registrations_edit': admin_reg,
            'perms_registrations_delete': admin_reg,
            'perms_registrations_settings': admin_reg,
        }

    # مستخدم عادي
    membership = active_membership_for(user)
    perms2 = permissions_for_membership(membership) if membership else {}
    modules2 = membership.tenant.modules if membership else {}

    # إذا كانت الشركة مفعّل لها accounting ولم توجد صلاحية accounting صريحة،
    # نربطها بصلاحية المالية حتى تظهر للمدير الذي لديه finance.
    if membership and (modules2 or {}).get('accounting', False) and 'accounting' not in (membership.permissions or {}):
        finance_perms = perms2.get('finance', {})
        perms2['accounting'] = {
            'view': finance_perms.get('view', False),
            'create': finance_perms.get('create', False),
            'edit': finance_perms.get('edit', False),
            'delete': finance_perms.get('delete', False),
            'export': finance_perms.get('export', False),
            'payroll': finance_perms.get('view', False),
        }

    reg_perms2 = perms2.get('registrations', {})
    return {
        'tenant_membership': membership,
        'tenant_permissions': perms2,
        'tenant_modules': modules2,
        'active_tenant_context': None,
        'perms_registrations_view': reg_perms2.get('view', False),
        'perms_registrations_create': reg_perms2.get('create', False),
        'perms_registrations_edit': reg_perms2.get('edit', False),
        'perms_registrations_delete': reg_perms2.get('delete', False),
        'perms_registrations_settings': reg_perms2.get('settings', False),
    }
