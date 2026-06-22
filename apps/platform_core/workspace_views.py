from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .navigation import active_membership_for, is_platform_admin, permissions_for_membership


@login_required
def home(request):
    if is_platform_admin(request.user):
        return redirect("platform_core:tenant_list")

    membership = active_membership_for(request.user)
    if not membership:
        return render(request, "workspace/home.html", {
            "tenant": None,
            "membership": None,
            "permissions": {},
        })

    return render(request, "workspace/home.html", {
        "tenant": membership.tenant,
        "membership": membership,
        "permissions": permissions_for_membership(membership),
    })



@login_required
def finance(request):
    if is_platform_admin(request.user):
        return redirect("payments:dashboard")

    membership = active_membership_for(request.user)
    permissions = permissions_for_membership(membership) if membership else {}

    return render(request, "workspace/finance.html", {
        "tenant": membership.tenant if membership else None,
        "membership": membership,
        "permissions": permissions,
    })



@login_required
def access_denied(request):
    return render(request, "workspace/access_denied.html", status=403)


# ============ إدارة الموظفين من لوحة مدير الشركة ============

@login_required
def workspace_members(request):
    membership = active_membership_for(request.user)
    if not membership or not membership.is_tenant_admin:
        return redirect('workspace:access_denied')
    tenant = membership.tenant
    members = tenant.memberships.select_related('user', 'role').all()
    return render(request, 'workspace/members.html', {
        'tenant': tenant, 'members': members, 'membership': membership,
    })


@login_required
def workspace_member_add(request):
    from django.contrib.auth import get_user_model
    from .models import TenantMembership
    from .forms import TenantManagerForm
    membership = active_membership_for(request.user)
    if not membership or not membership.is_tenant_admin:
        return redirect('workspace:access_denied')
    tenant = membership.tenant
    if request.method == 'POST':
        form = TenantManagerForm(request.POST, tenant_modules=tenant.modules)
        if form.is_valid():
            User = get_user_model()
            email = form.cleaned_data['email'].strip().lower()
            full_name = form.cleaned_data.get('full_name', '').strip()
            password = form.cleaned_data.get('password')
            username = form.cleaned_data.get('username') or email.split('@')[0]
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                user = User()
                user.username = username
                user.email = email
                if full_name:
                    parts = full_name.split(' ', 1)
                    user.first_name = parts[0]
                    user.last_name = parts[1] if len(parts) > 1 else ''
                if password:
                    user.set_password(password)
                else:
                    user.set_unusable_password()
                user.save()
            perms = form.permissions_payload()
            role_name = form.cleaned_data.get('role_name', '').strip()
            is_admin = form.cleaned_data.get('is_tenant_admin', False)
            m, _ = TenantMembership.objects.get_or_create(tenant=tenant, user=user)
            m.permissions = perms
            m.role_name = role_name
            m.is_tenant_admin = bool(is_admin)
            m.is_active = True
            m.save()
            from django.contrib import messages
            messages.success(request, f'تم إضافة {user.username} بنجاح')
            return redirect('workspace:members')
    else:
        form = TenantManagerForm(tenant_modules=tenant.modules)
    return render(request, 'workspace/member_add.html', {
        'tenant': tenant, 'form': form, 'membership': membership,
    })


@login_required
def workspace_member_edit(request, membership_pk):
    from django.contrib import messages
    from .models import TenantMembership
    from .forms import default_permissions
    membership = active_membership_for(request.user)
    if not membership or not membership.is_tenant_admin:
        return redirect('workspace:access_denied')
    tenant = membership.tenant
    target = TenantMembership.objects.get(pk=membership_pk, tenant=tenant)
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        if full_name:
            parts = full_name.split(' ', 1)
            target.user.first_name = parts[0]
            target.user.last_name = parts[1] if len(parts) > 1 else ''
            target.user.save(update_fields=['first_name', 'last_name'])
        target.role_name = request.POST.get('role_name', '').strip()
        target.is_tenant_admin = request.POST.get('is_tenant_admin') == 'on'
        perms = default_permissions()
        for section in perms:
            enabled = request.POST.get(f'perm_{section}') == 'on'
            for action in perms[section]:
                perms[section][action] = enabled
        target.permissions = perms
        target.save()
        messages.success(request, 'تم تحديث بيانات الموظف')
        return redirect('workspace:members')
    return render(request, 'workspace/member_edit.html', {
        'tenant': tenant, 'target': target, 'membership': membership,
        'modules': tenant.modules,
    })


@login_required
def workspace_roles(request):
    from django.contrib import messages
    from .models import TenantRole
    from .forms import default_permissions
    membership = active_membership_for(request.user)
    if not membership or not membership.is_tenant_admin:
        return redirect('workspace:access_denied')
    tenant = membership.tenant
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            perms = default_permissions()
            for section in perms:
                enabled = request.POST.get(f'perm_{section}') == 'on'
                for action in perms[section]:
                    perms[section][action] = enabled
            TenantRole.objects.create(
                tenant=tenant, name=name,
                description=request.POST.get('description', '').strip(),
                permissions=perms
            )
            messages.success(request, f'تم إنشاء الدور: {name}')
        return redirect('workspace:roles')
    roles = tenant.roles.all()
    return render(request, 'workspace/roles.html', {
        'tenant': tenant, 'roles': roles, 'membership': membership,
        'modules': tenant.modules,
    })


@login_required
def workspace_member_reset_password(request, membership_pk):
    from django.contrib import messages
    from .models import TenantMembership
    membership = active_membership_for(request.user)
    if not membership or not membership.is_tenant_admin:
        return redirect('workspace:access_denied')
    from django.shortcuts import get_object_or_404
    target = get_object_or_404(TenantMembership, pk=membership_pk, tenant=membership.tenant)
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        if len(new_password) < 6:
            messages.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
        else:
            target.user.set_password(new_password)
            target.user.save()
            messages.success(request, f'تم تغيير كلمة مرور {target.user.username} بنجاح')
            return redirect('workspace:members')
    return render(request, 'workspace/reset_password.html', {
        'target': target, 'tenant': membership.tenant,
    })
