from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import TenantForm, TenantManagerForm, MembershipPermissionsForm
from .models import Tenant, TenantMembership, TenantRole


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

    context = {
        "tenants": tenants,
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
