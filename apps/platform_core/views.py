from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import TenantForm, TenantManagerForm, MembershipPermissionsForm
from .models import Tenant, TenantMembership, TenantRole, default_permissions


def _platform_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


platform_required = user_passes_test(_platform_admin)


def _has_field(model, field_name):
    return any(field.name == field_name for field in model._meta.fields)


def _set_if_has(obj, field_name, value):
    if _has_field(obj.__class__, field_name):
        setattr(obj, field_name, value)


def _tenant_ordering():
    if _has_field(Tenant, "created_at"):
        return "-created_at"
    return "name"


def _unique_username(User, wanted):
    wanted = (wanted or "manager").strip().replace(" ", "_")
    username = wanted
    counter = 1
    username_field = getattr(User, "USERNAME_FIELD", "username")

    while User.objects.filter(**{username_field: username}).exists():
        counter += 1
        username = f"{wanted}_{counter}"

    return username


def _manager_role_code(tenant):
    try:
        code_field = TenantRole._meta.get_field("code")
        if getattr(code_field, "unique", False):
            return f"tenant_admin_{tenant.pk}"
    except Exception:
        pass
    return "tenant_admin"


def _get_or_create_manager_role(tenant, permissions):
    lookup = {}

    if _has_field(TenantRole, "tenant"):
        lookup["tenant"] = tenant
    if _has_field(TenantRole, "code"):
        lookup["code"] = _manager_role_code(tenant)

    role = TenantRole.objects.filter(**lookup).first() if lookup else None
    if role:
        _set_if_has(role, "permissions", permissions)
        role.save()
        return role

    role = TenantRole()
    _set_if_has(role, "tenant", tenant)
    _set_if_has(role, "name", "مدير الشركة")
    _set_if_has(role, "code", _manager_role_code(tenant))
    _set_if_has(role, "permissions", permissions)
    _set_if_has(role, "is_system", False)

    try:
        role.save()
    except IntegrityError:
        role = TenantRole.objects.filter(code=_manager_role_code(tenant)).first()
        if not role:
            raise

    return role


@login_required
@platform_required
def home(request):
    return redirect("platform_core:tenant_list")


@login_required
@platform_required
def tenant_list(request):
    tenants = Tenant.objects.all().order_by(_tenant_ordering())

    # أسماء الوحدات بالعربي
    from .forms import MODULE_CHOICES
    module_labels = dict(MODULE_CHOICES)

    cards = []
    for t in tenants:
        memberships = TenantMembership.objects.filter(tenant=t)
        admin = memberships.filter(is_tenant_admin=True).first()
        mods = t.modules or {}
        active_mods = [module_labels.get(code, code) for code, on in mods.items() if on and code in module_labels]
        cards.append({
            "tenant": t,
            "admin_username": admin.user.username if admin else None,
            "members_count": memberships.count(),
            "active_modules": active_mods,
        })

    context = {
        "tenants": tenants,
        "cards": cards,
        "total_tenants": tenants.count(),
        "active_tenants": Tenant.objects.filter(status="active").count() if _has_field(Tenant, "status") else 0,
        "membership_count": TenantMembership.objects.count(),
    }
    return render(request, "platform_core/tenant_list.html", context)


@login_required
@platform_required
def tenant_detail(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)

    try:
        memberships = TenantMembership.objects.select_related("user", "role").filter(tenant=tenant)
    except Exception:
        memberships = TenantMembership.objects.filter(tenant=tenant)

    context = {
        "tenant": tenant,
        "memberships": memberships,
        "module_items": list((tenant.modules or {}).items()) if hasattr(tenant, "modules") else [],
        "limit_items": list((tenant.limits or {}).items()) if hasattr(tenant, "limits") else [],
        "manager_form": TenantManagerForm(tenant_modules=tenant.modules),
        "memberships": tenant.memberships.select_related("user", "role").all(),
    }
    return render(request, "platform_core/tenant_detail.html", context)


@login_required
@platform_required
def tenant_create(request):
    if request.method == "POST":
        form = TenantForm(request.POST)
        if form.is_valid():
            tenant = form.save()
            messages.success(request, "تم إنشاء الشركة بنجاح.")
            return redirect("platform_core:tenant_detail", pk=tenant.pk)
    else:
        form = TenantForm()

    return render(request, "platform_core/tenant_form.html", {"form": form, "mode": "create"})


@login_required
@platform_required
def tenant_edit(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)

    if request.method == "POST":
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث بيانات الشركة.")
            return redirect("platform_core:tenant_detail", pk=tenant.pk)
    else:
        form = TenantForm(instance=tenant)

    return render(request, "platform_core/tenant_form.html", {"form": form, "tenant": tenant, "mode": "edit"})


@login_required
@platform_required
@require_POST
def tenant_delete(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    name = tenant.name
    tenant.delete()
    messages.success(request, f"تم حذف الشركة: {name}")
    return redirect("platform_core:tenant_list")


@login_required
@platform_required
@require_POST
def tenant_add_manager(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    form = TenantManagerForm(request.POST, tenant_modules=tenant.modules)

    if not form.is_valid():
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        return redirect("platform_core:tenant_detail", pk=tenant.pk)

    User = get_user_model()
    email = form.cleaned_data["email"].strip().lower()
    username = form.cleaned_data.get("username") or email.split("@")[0]
    full_name = form.cleaned_data.get("full_name", "").strip()
    password = form.cleaned_data.get("password")

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        username_field = getattr(User, "USERNAME_FIELD", "username")
        user = User()
        if username_field == "email":
            setattr(user, username_field, email)
        else:
            setattr(user, username_field, _unique_username(User, username))
        if hasattr(user, "email"):
            user.email = email
        if full_name and hasattr(user, "first_name"):
            parts = full_name.split(" ", 1)
            user.first_name = parts[0]
            if len(parts) > 1 and hasattr(user, "last_name"):
                user.last_name = parts[1]
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()

    permissions = form.permissions_payload()
    role = _get_or_create_manager_role(tenant, permissions)

    membership = TenantMembership.objects.filter(tenant=tenant, user=user).first()
    if not membership:
        membership = TenantMembership(tenant=tenant, user=user)

    _set_if_has(membership, "role", role)
    # حفظ المسمى الوظيفي
    role_name = form.cleaned_data.get("role_name", "").strip()
    if role_name and hasattr(membership, "role_name"):
        membership.role_name = role_name
    # تحديد مدير الشركة
    is_admin = form.cleaned_data.get("is_tenant_admin", False)
    if hasattr(membership, "is_tenant_admin"):
        membership.is_tenant_admin = bool(is_admin)
    _set_if_has(membership, "permissions", permissions)
    _set_if_has(membership, "is_active", True)
    membership.save()
    # expire_user_sessions — نمسح session المستخدم إن وُجد
    try:
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            data = session.get_decoded()
            if str(data.get("_auth_user_id")) == str(user.id):
                session.delete()
    except Exception:
        pass

    messages.success(request, "تم ربط مدير الشركة بنجاح.")
    return redirect("platform_core:tenant_detail", pk=tenant.pk)


@login_required
@platform_required
@require_POST
def tenant_member_toggle(request, membership_pk):
    membership = get_object_or_404(TenantMembership, pk=membership_pk)
    tenant_pk = membership.tenant_id

    if _has_field(TenantMembership, "is_active"):
        membership.is_active = not membership.is_active
        membership.save(update_fields=["is_active"])
        messages.success(request, "تم تحديث حالة العضو.")
    else:
        messages.info(request, "هذا العضو لا يحتوي حقل تفعيل.")

    return redirect("platform_core:tenant_detail", pk=tenant_pk)


@login_required
@platform_required
@require_POST
def tenant_member_delete(request, membership_pk):
    membership = get_object_or_404(TenantMembership, pk=membership_pk)
    tenant_pk = membership.tenant_id
    membership.delete()
    messages.success(request, "تم حذف العضو من الشركة.")
    return redirect("platform_core:tenant_detail", pk=tenant_pk)



@login_required
@platform_required
def tenant_member_permissions(request, membership_pk):
    membership = get_object_or_404(TenantMembership.objects.select_related("tenant", "user", "role"), pk=membership_pk)

    if request.method == "POST":
        form = MembershipPermissionsForm(request.POST, membership=membership)
        if form.is_valid():
            permissions = form.permissions_payload()
            if _has_field(TenantMembership, "permissions"):
                # INEXC_SPARK_FORM_PERMISSION
                if "registrations" in permissions:
                    reg = permissions.get("registrations") or {}
                    forms = reg.get("forms") if isinstance(reg.get("forms"), dict) else {}
                    forms["spark"] = bool(request.POST.get("registrations__forms__spark") or request.POST.get("spark_registration_form"))
                    reg["forms"] = forms
                    permissions["registrations"] = reg
                membership.permissions = permissions
                membership.save(update_fields=["permissions"])
                messages.success(request, "تم تحديث صلاحيات العضو.")
            else:
                messages.error(request, "موديل العضوية لا يحتوي حقل permissions.")
            return redirect("platform_core:tenant_detail", pk=membership.tenant_id)
    else:
        form = MembershipPermissionsForm(membership=membership)

    grouped_permissions = []
    for group in form.permission_groups:
        grouped_permissions.append({
            "label": group["label"],
            "fields": [form[field_name] for field_name in group["fields"]],
        })

    return render(request, "platform_core/tenant_member_permissions.html", {
        "membership": membership,
        "tenant": membership.tenant,
        "form": form,
        "grouped_permissions": grouped_permissions,
    })



@login_required
@platform_required
def tenant_members(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    memberships = TenantMembership.objects.select_related("user", "role").filter(tenant=tenant)

    return render(request, "platform_core/tenant_members.html", {
        "tenant": tenant,
        "memberships": memberships,
        "manager_form": TenantManagerForm(tenant_modules=tenant.modules),
        "memberships": tenant.memberships.select_related("user", "role").all(),
    })


# ============ تبديل سياق الشركة للمدير العام ============

@login_required
def switch_tenant_context(request, tenant_id):
    """يتيح للمدير العام الدخول على بيانات شركة معينة."""
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('/')
    from .models import Tenant
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    request.session['active_tenant_id'] = tenant_id
    request.session['active_tenant_name'] = tenant.name
    messages.success(request, f'أنت الآن تتصفح بيانات: {tenant.name}')
    return redirect('payments:dashboard')


@login_required
def clear_tenant_context(request):
    """يعود للوحة المدير العام."""
    request.session.pop('active_tenant_id', None)
    request.session.pop('active_tenant_name', None)
    messages.success(request, 'عدت للوحة المدير العام')
    return redirect('payments:dashboard')

@login_required
@platform_required
def tenant_add_member_page(request, pk):
    """صفحة منفصلة لإضافة موظف."""
    tenant = get_object_or_404(Tenant, pk=pk)
    form = TenantManagerForm(tenant_modules=tenant.modules)
    return render(request, "platform_core/member_form.html", {
        "tenant": tenant,
        "form": form,
    })

# ============ إدارة الأدوار/المسميات الوظيفية ============

@login_required
@platform_required
def tenant_roles(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    roles = tenant.roles.all()
    return render(request, 'platform_core/role_list.html', {
        'tenant': tenant, 'roles': roles,
    })


@login_required
@platform_required
def tenant_role_create(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, 'اسم الدور مطلوب')
            return redirect('platform_core:tenant_roles', pk=pk)
        # بناء الصلاحيات من POST
        perms = default_permissions()
        for section in perms:
            enabled = request.POST.get(f'perm_{section}') == 'on'
            for action in perms[section]:
                perms[section][action] = enabled
        # صلاحية نموذج سبارك (تُحفظ داخل registrations.forms.spark)
        spark_on = request.POST.get('spark_registration_form') == 'on'
        perms.setdefault('registrations', {})
        reg_forms = perms['registrations'].get('forms')
        if not isinstance(reg_forms, dict):
            reg_forms = {}
        reg_forms['spark'] = spark_on
        perms['registrations']['forms'] = reg_forms
        TenantRole.objects.create(
            tenant=tenant, name=name, description=description, permissions=perms
        )
        messages.success(request, f'تم إنشاء الدور: {name}')
        return redirect('platform_core:tenant_roles', pk=pk)
    return render(request, 'platform_core/role_form.html', {
        'tenant': tenant, 'role': None,
        'modules': tenant.modules,
    })


@login_required
@platform_required
def tenant_role_edit(request, pk, role_pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    role = get_object_or_404(TenantRole, pk=role_pk, tenant=tenant)
    if request.method == 'POST':
        role.name = request.POST.get('name', role.name).strip()
        role.description = request.POST.get('description', '').strip()
        perms = default_permissions()
        for section in perms:
            enabled = request.POST.get(f'perm_{section}') == 'on'
            for action in perms[section]:
                perms[section][action] = enabled
        # صلاحية نموذج سبارك (تُحفظ داخل registrations.forms.spark)
        spark_on = request.POST.get('spark_registration_form') == 'on'
        perms.setdefault('registrations', {})
        reg_forms = perms['registrations'].get('forms')
        if not isinstance(reg_forms, dict):
            reg_forms = {}
        reg_forms['spark'] = spark_on
        perms['registrations']['forms'] = reg_forms
        role.permissions = perms
        role.save()
        messages.success(request, f'تم تحديث الدور: {role.name}')
        return redirect('platform_core:tenant_roles', pk=pk)
    return render(request, 'platform_core/role_form.html', {
        'tenant': tenant, 'role': role,
        'modules': tenant.modules,
    })


@login_required
@platform_required
@require_POST
def tenant_role_delete(request, pk, role_pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    role = get_object_or_404(TenantRole, pk=role_pk, tenant=tenant)
    if role.is_system:
        messages.error(request, 'لا يمكن حذف دور النظام')
    else:
        role.delete()
        messages.success(request, 'تم حذف الدور')
    return redirect('platform_core:tenant_roles', pk=pk)


# ============ تعديل الموظف + إعادة كلمة المرور ============

@login_required
@platform_required
def tenant_member_edit(request, membership_pk):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    membership = get_object_or_404(TenantMembership, pk=membership_pk)
    tenant = membership.tenant
    if request.method == 'POST':
        user = membership.user
        full_name = request.POST.get('full_name', '').strip()
        if full_name:
            parts = full_name.split(' ', 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ''
            user.save(update_fields=['first_name', 'last_name'])
        role_name = request.POST.get('role_name', '').strip()
        if hasattr(membership, 'role_name'):
            membership.role_name = role_name
        is_admin = request.POST.get('is_tenant_admin') == 'on'
        if hasattr(membership, 'is_tenant_admin'):
            membership.is_tenant_admin = is_admin
        perms = default_permissions()
        for section in perms:
            enabled = request.POST.get(f'perm_{section}') == 'on'
            for action in perms[section]:
                perms[section][action] = enabled
        # صلاحية نموذج سبارك (تُحفظ داخل registrations.forms.spark)
        spark_on = request.POST.get('spark_registration_form') == 'on'
        perms.setdefault('registrations', {})
        reg_forms = perms['registrations'].get('forms')
        if not isinstance(reg_forms, dict):
            reg_forms = {}
        reg_forms['spark'] = spark_on
        perms['registrations']['forms'] = reg_forms
        membership.permissions = perms
        membership.save()
        messages.success(request, f'تم تحديث بيانات {user.username}')
        return redirect('platform_core:tenant_detail', pk=tenant.pk)
    return render(request, 'platform_core/member_edit.html', {
        'membership': membership,
        'tenant': tenant,
        'modules': tenant.modules,
    })


@login_required
@platform_required
@require_POST
def tenant_member_reset_password(request, membership_pk):
    from django.core.mail import send_mail
    from django.utils.crypto import get_random_string
    membership = get_object_or_404(TenantMembership, pk=membership_pk)
    user = membership.user
    new_password = get_random_string(10)
    user.set_password(new_password)
    user.save()
    try:
        send_mail(
            subject='إعادة تعيين كلمة المرور',
            message=f'مرحباً {user.get_full_name() or user.username},\n\nكلمة المرور الجديدة: {new_password}\n\nيُرجى تغييرها فور تسجيل الدخول.',
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )
        messages.success(request, f'تم إرسال كلمة المرور الجديدة لـ {user.email}')
    except Exception as e:
        messages.error(request, f'فشل الإرسال: {e} — كلمة المرور الجديدة: {new_password}')
    return redirect('platform_core:tenant_detail', pk=membership.tenant.pk)


@login_required
@platform_required
def tenant_member_set_password(request, membership_pk):
    from django.contrib import messages
    membership = get_object_or_404(TenantMembership, pk=membership_pk)
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        if len(new_password) < 6:
            messages.error(request, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
        else:
            membership.user.set_password(new_password)
            membership.user.save()
            messages.success(request, f'تم تغيير كلمة مرور {membership.user.username} بنجاح')
            return redirect('platform_core:tenant_detail', pk=membership.tenant.pk)
    return render(request, 'platform_core/set_password.html', {
        'membership': membership, 'tenant': membership.tenant,
    })


@login_required
@platform_required
def platform_settings(request):
    """إعدادات المنصة (النسب) للمدير العام."""
    from .models import PlatformSettings
    ps = PlatformSettings.get_solo()
    if request.method == 'POST':
        try:
            ps.commission_platform_stripe = float(request.POST.get('commission_platform_stripe', 7) or 7)
            ps.commission_own_stripe = float(request.POST.get('commission_own_stripe', 2) or 2)
            ps.payout_hold_days = int(request.POST.get('payout_hold_days', 12) or 12)
            ps.express_payout_rate = float(request.POST.get('express_payout_rate', 10) or 10)
            ps.save()
            messages.success(request, 'تم حفظ الإعدادات بنجاح')
        except (ValueError, TypeError):
            messages.error(request, 'قيمة غير صالحة')
        return redirect('platform_core:platform_settings')
    return render(request, 'platform_core/platform_settings.html', {'ps': ps})


@login_required
@platform_required
def platform_finance(request):
    """لوحة مالية للمدير العام: مستحقات كل شركة."""
    from .models import Tenant, PlatformSettings
    from apps.payments.models import Payment
    from decimal import Decimal
    ps = PlatformSettings.get_solo()
    rows = []
    grand_total = Decimal('0')
    grand_commission = Decimal('0')
    grand_net = Decimal('0')
    for t in Tenant.objects.all():
        pays = Payment.objects.filter(tenant=t, status='paid')
        total = sum((pp.amount or Decimal('0')) for pp in pays)
        total = Decimal(str(total))
        # النسبة: من الشركة إن وُجدت، وإلا الافتراضي حسب النوع
        if t.commission_rate is not None:
            rate = Decimal(str(t.commission_rate))
        elif t.stripe_mode == 'own':
            rate = Decimal(str(ps.commission_own_stripe))
        else:
            rate = Decimal(str(ps.commission_platform_stripe))
        commission = (total * rate / Decimal('100')).quantize(Decimal('0.01'))
        net = (total - commission).quantize(Decimal('0.01'))
        grand_total += total
        grand_commission += commission
        grand_net += net
        rows.append({
            'tenant': t,
            'count': pays.count(),
            'total': total,
            'rate': rate,
            'commission': commission,
            'net': net,
            'mode': t.stripe_mode,
            'bank_ok': bool(t.bank_iban or t.bank_account_number),
        })
    return render(request, 'platform_core/platform_finance.html', {
        'rows': rows,
        'grand_total': grand_total,
        'grand_commission': grand_commission,
        'grand_net': grand_net,
        'ps': ps,
    })


@login_required
@platform_required
def tenant_wizard(request):
    """معالج موحّد: إنشاء شركة + تفعيل وحدات + إنشاء حساب المدير، في خطوة واحدة."""
    from .forms import MODULE_CHOICES
    from .models import default_tenant_modules
    User = get_user_model()
    created_info = None

    if request.method == "POST":
        company_name = request.POST.get("company_name", "").strip()
        mgr_full_name = request.POST.get("mgr_full_name", "").strip()
        mgr_username = request.POST.get("mgr_username", "").strip()
        mgr_email = request.POST.get("mgr_email", "").strip().lower()
        mgr_password = request.POST.get("mgr_password", "").strip()

        errors = []
        if not company_name:
            errors.append("اسم الشركة مطلوب")
        if not mgr_username:
            errors.append("اسم المستخدم للمدير مطلوب")
        if not mgr_password:
            errors.append("كلمة المرور مطلوبة")
        if User.objects.filter(username=mgr_username).exists():
            errors.append(f"اسم المستخدم '{mgr_username}' مستخدم بالفعل")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "platform_core/tenant_wizard.html", {
                "module_choices": MODULE_CHOICES,
                "form_data": request.POST,
            })

        # 1) إنشاء الشركة + الوحدات
        modules = default_tenant_modules()
        for code, _ in MODULE_CHOICES:
            modules[code] = (request.POST.get(f"module_{code}") == "on")
        tenant = Tenant.objects.create(
            name=company_name,
            owner_name=mgr_full_name,
            owner_email=mgr_email,
            modules=modules,
        )

        # 2) إنشاء حساب المدير
        user = User(username=mgr_username, email=mgr_email)
        if mgr_full_name:
            parts = mgr_full_name.split(" ", 1)
            user.first_name = parts[0]
            if len(parts) > 1:
                user.last_name = parts[1]
        user.set_password(mgr_password)
        user.save()

        # 3) العضوية كمدير شركة بكامل الصلاحيات
        perms = default_permissions()
        for sec in perms:
            for act in perms[sec]:
                perms[sec][act] = True
        TenantMembership.objects.create(
            tenant=tenant, user=user,
            role_name="مدير الشركة",
            is_tenant_admin=True,
            is_active=True,
            permissions=perms,
        )

        messages.success(request, f"تم إنشاء شركة '{company_name}' ومديرها بنجاح")
        created_info = {
            "company": company_name,
            "username": mgr_username,
            "password": mgr_password,
            "tenant_pk": tenant.pk,
        }
        return render(request, "platform_core/tenant_wizard.html", {
            "module_choices": MODULE_CHOICES,
            "created_info": created_info,
        })

    return render(request, "platform_core/tenant_wizard.html", {
        "module_choices": MODULE_CHOICES,
    })


@login_required
@platform_required
def platform_payouts(request):
    """إدارة طلبات السحب للمدير العام."""
    from .models import PayoutRequest
    from django.utils import timezone

    if request.method == "POST":
        req_id = request.POST.get("request_id")
        action = request.POST.get("action")
        note = request.POST.get("admin_note", "").strip()
        try:
            pr = PayoutRequest.objects.get(pk=req_id)
            if action == "paid":
                pr.status = "paid"
                pr.processed_at = timezone.now()
                pr.transfer_reference = request.POST.get("transfer_reference", "").strip()
                _td = request.POST.get("transfer_date", "").strip()
                if _td:
                    pr.transfer_date = _td
                if request.FILES.get("transfer_receipt"):
                    pr.transfer_receipt = request.FILES["transfer_receipt"]
                messages.success(request, f"تم تأكيد تحويل {pr.net_amount} لـ {pr.tenant.name}")
            elif action == "rejected":
                pr.status = "rejected"
                pr.processed_at = timezone.now()
                messages.success(request, f"تم رفض طلب {pr.tenant.name}")
            if note:
                pr.admin_note = note
            pr.save()
        except PayoutRequest.DoesNotExist:
            messages.error(request, "الطلب غير موجود")
        return redirect("platform_core:platform_payouts")

    status_filter = request.GET.get("status", "pending")
    qs = PayoutRequest.objects.select_related("tenant")
    if status_filter and status_filter != "all":
        qs = qs.filter(status=status_filter)

    pending_count = PayoutRequest.objects.filter(status="pending").count()
    return render(request, "platform_core/platform_payouts.html", {
        "requests": qs,
        "status_filter": status_filter,
        "pending_count": pending_count,
    })

def subscription_expired(request):
    from django.shortcuts import render
    return render(request, "subscription_expired.html")
