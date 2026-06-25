from django.db import models
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
    from .models import TenantRole
    import json as _json
    roles = TenantRole.objects.filter(tenant=tenant)
    roles_json = _json.dumps({str(r.pk): r.permissions for r in roles})
    return render(request, 'workspace/member_add.html', {
        'tenant': tenant, 'form': form, 'membership': membership,
        'roles': roles, 'roles_json': roles_json,
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


@login_required
def workspace_registration_settings(request):
    from apps.platform_core.models import Tenant, TenantMembership
    from apps.platform_core.navigation import active_membership_for, is_platform_admin
    if is_platform_admin(request.user):
        tenant = Tenant.objects.first()
    else:
        membership = TenantMembership.objects.filter(user=request.user).first()
        if not membership:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("غير مصرح")
        tenant = membership.tenant
    if request.method == "POST":
        tenant.emailjs_service_id = request.POST.get("emailjs_service_id", "").strip()
        tenant.emailjs_template_id = request.POST.get("emailjs_template_id", "").strip()
        tenant.emailjs_public_key = request.POST.get("emailjs_public_key", "").strip()
        tenant.emailjs_private_key = request.POST.get("emailjs_private_key", "").strip()
        tenant.registration_admin_email = request.POST.get("registration_admin_email", "").strip()
        # تفعيل/تعطيل نظام التسجيل
        modules = tenant.modules or {}
        modules["registrations"] = request.POST.get("enable_registrations") == "on"
        tenant.modules = modules
        tenant.save()
        from django.contrib import messages
        messages.success(request, "تم حفظ الإعدادات بنجاح")
        return redirect("workspace:registration_settings")
    return render(request, "workspace/registration_settings.html", {"tenant": tenant})


@login_required
def workspace_stripe_settings(request):
    from apps.platform_core.models import Tenant, TenantMembership, PlatformSettings
    from apps.platform_core.navigation import active_membership_for, is_platform_admin
    if is_platform_admin(request.user):
        tenant = Tenant.objects.first()
    else:
        membership = active_membership_for(request.user)
        if not membership or not membership.is_tenant_admin:
            return redirect("workspace:access_denied")
        tenant = membership.tenant

    modules = tenant.modules or {}
    if not modules.get("stripe") and not is_platform_admin(request.user):
        return redirect("workspace:access_denied")

    ps = PlatformSettings.get_solo()

    if request.method == "POST":
        mode = request.POST.get("stripe_mode", "platform").strip()
        if mode not in ("platform", "own"):
            mode = "platform"
        tenant.stripe_mode = mode
        if mode == "own":
            tenant.stripe_secret_key = request.POST.get("stripe_secret_key", "").strip()
            tenant.stripe_publishable_key = request.POST.get("stripe_publishable_key", "").strip()
            tenant.stripe_webhook_secret = request.POST.get("stripe_webhook_secret", "").strip()
            tenant.commission_rate = ps.commission_own_stripe
        else:
            tenant.bank_name = request.POST.get("bank_name", "").strip()
            tenant.bank_country = request.POST.get("bank_country", "").strip()
            tenant.bank_account_holder = request.POST.get("bank_account_holder", "").strip()
            tenant.bank_iban = request.POST.get("bank_iban", "").strip()
            tenant.bank_account_number = request.POST.get("bank_account_number", "").strip()
            tenant.bank_swift = request.POST.get("bank_swift", "").strip()
            tenant.bank_currency = request.POST.get("bank_currency", "").strip()
            tenant.commission_rate = ps.commission_platform_stripe
        tenant.save()
        from django.contrib import messages
        messages.success(request, "تم حفظ إعدادات الدفع بنجاح")
        return redirect("workspace:stripe_settings")

    return render(request, "workspace/stripe_settings.html", {
        "tenant": tenant,
        "platform_settings": ps,
    })


@login_required
def workspace_finance_board(request):
    """لوحة مالية للشركة: دفعاتها وصافيها المستحق (شفافية)."""
    from apps.platform_core.models import Tenant, PlatformSettings
    from apps.platform_core.navigation import active_membership_for, is_platform_admin
    from apps.payments.models import Payment
    from decimal import Decimal
    if is_platform_admin(request.user):
        tenant = Tenant.objects.first()
    else:
        membership = active_membership_for(request.user)
        if not membership or not membership.is_tenant_admin:
            return redirect("workspace:access_denied")
        tenant = membership.tenant

    modules = tenant.modules or {}
    if not modules.get("stripe") and not is_platform_admin(request.user):
        return redirect("workspace:access_denied")

    ps = PlatformSettings.get_solo()
    pays = Payment.objects.filter(tenant=tenant, status='paid').order_by('-created_at')
    total = Decimal(str(sum((pp.amount or Decimal('0')) for pp in pays)))

    if tenant.commission_rate is not None:
        rate = Decimal(str(tenant.commission_rate))
    elif tenant.stripe_mode == 'own':
        rate = Decimal(str(ps.commission_own_stripe))
    else:
        rate = Decimal(str(ps.commission_platform_stripe))

    commission = (total * rate / Decimal('100')).quantize(Decimal('0.01'))
    net = (total - commission).quantize(Decimal('0.01'))

    return render(request, 'workspace/finance_board.html', {
        'tenant': tenant,
        'payments': pays[:50],
        'total': total,
        'rate': rate,
        'commission': commission,
        'net': net,
        'mode': tenant.stripe_mode,
        'bank_ok': bool(tenant.bank_iban or tenant.bank_account_number),
    })


def _payout_available(tenant, ps, express=False):
    """يحسب المبلغ القابل للسحب. عادي: دفعات مرّ عليها hold_days. سريع: الكل."""
    from apps.payments.models import Payment
    from django.utils import timezone
    from datetime import timedelta
    from decimal import Decimal

    pays = Payment.objects.filter(tenant=tenant, status='paid')
    if not express:
        cutoff = timezone.now() - timedelta(days=ps.payout_hold_days)
        pays = pays.filter(created_at__lte=cutoff)

    # نستبعد المبالغ المسحوبة/المطلوبة سابقاً (المعلّقة أو المدفوعة)
    from apps.platform_core.models import PayoutRequest
    already = PayoutRequest.objects.filter(
        tenant=tenant, status__in=['pending', 'paid']
    ).aggregate(s=models.Sum('gross_amount'))['s'] or Decimal('0')

    gross = Decimal(str(sum((pp.amount or Decimal('0')) for pp in pays)))
    gross_available = gross - Decimal(str(already))
    if gross_available < 0:
        gross_available = Decimal('0')
    return gross_available


@login_required
def workspace_payout_request(request):
    """طلب سحب أموال من الشركة."""
    from apps.platform_core.models import Tenant, PlatformSettings, PayoutRequest
    from apps.platform_core.navigation import active_membership_for, is_platform_admin
    from decimal import Decimal
    from django.utils import timezone

    if is_platform_admin(request.user):
        tenant = Tenant.objects.first()
    else:
        membership = active_membership_for(request.user)
        if not membership or not membership.is_tenant_admin:
            return redirect("workspace:access_denied")
        tenant = membership.tenant

    modules = tenant.modules or {}
    if not modules.get("stripe") and not is_platform_admin(request.user):
        return redirect("workspace:access_denied")

    ps = PlatformSettings.get_solo()

    # النسبة العادية حسب نوع الحساب
    if tenant.stripe_mode == 'own':
        normal_rate = Decimal(str(ps.commission_own_stripe))
    else:
        normal_rate = Decimal(str(ps.commission_platform_stripe))
    express_rate = Decimal(str(ps.express_payout_rate))

    normal_available = _payout_available(tenant, ps, express=False)
    express_available = _payout_available(tenant, ps, express=True)

    if request.method == "POST":
        ptype = request.POST.get("payout_type", "normal")
        from django.contrib import messages
        if ptype == "express":
            gross = express_available
            rate = express_rate
        else:
            gross = normal_available
            rate = normal_rate

        if gross <= 0:
            messages.error(request, "لا يوجد رصيد قابل للسحب حالياً")
            return redirect("workspace:payout_request")

        commission = (gross * rate / Decimal('100')).quantize(Decimal('0.01'))
        net = (gross - commission).quantize(Decimal('0.01'))

        PayoutRequest.objects.create(
            tenant=tenant,
            requested_by=request.user,
            payout_type=ptype,
            gross_amount=gross,
            commission_rate=rate,
            commission_amount=commission,
            net_amount=net,
            status='pending',
        )
        messages.success(request, "تم إرسال طلب السحب بنجاح. سيُراجَع من قبل الإدارة.")
        return redirect("workspace:payout_request")

    requests_list = PayoutRequest.objects.filter(tenant=tenant)
    return render(request, "workspace/payout_request.html", {
        "tenant": tenant,
        "ps": ps,
        "normal_rate": normal_rate,
        "express_rate": express_rate,
        "normal_available": normal_available,
        "express_available": express_available,
        "requests_list": requests_list,
        "bank_ok": bool(tenant.bank_iban or tenant.bank_account_number),
    })
