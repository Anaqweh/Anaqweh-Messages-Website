from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect

from .models import Employee


def _tenant_for_request(request):
    try:
        active_tenant_id = request.GET.get("company") or request.session.get("active_tenant_id")
        if active_tenant_id and str(active_tenant_id).isdigit():
            from apps.platform_core.models import Tenant
            tenant = Tenant.objects.filter(pk=int(active_tenant_id)).first()
            if tenant:
                return tenant
    except Exception:
        pass

    if request.user.is_superuser:
        # GM_PLATFORM_DEFAULT:
        # None means platform records only in scoped query helpers, not all companies.
        return None

    try:
        from apps.platform_core.navigation import active_membership_for
        membership = active_membership_for(request.user)
        return membership.tenant if membership else None
    except Exception:
        return None


def _can_access_accounting(request):
    if request.user.is_superuser:
        return True

    try:
        from apps.platform_core.navigation import active_membership_for, permissions_for_membership
        membership = active_membership_for(request.user)
        if not membership:
            return False

        modules = membership.tenant.modules or {}
        perms = permissions_for_membership(membership) or {}
        finance = perms.get("finance", {})
        accounting = perms.get("accounting", {})

        return bool(
            membership.is_tenant_admin
            or modules.get("accounting")
            or accounting.get("view")
            or accounting.get("payroll")
            or finance.get("view")
        )
    except Exception:
        return False


def _employees_qs(request):
    qs = Employee.objects.all()
    tenant = _tenant_for_request(request)

    field_names = {f.name for f in Employee._meta.fields}
    if tenant is not None and "tenant" in field_names:
        qs = qs.filter(tenant=tenant)
    elif request.user.is_superuser and "tenant" in field_names:
        qs = qs.filter(tenant__isnull=True)
    elif not request.user.is_superuser:
        qs = qs.none()

    return qs


def _decimal_value(obj, field, default="0"):
    try:
        value = getattr(obj, field, default) or default
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _net_salary(employee):
    if hasattr(employee, "net_salary"):
        try:
            return Decimal(str(employee.net_salary or 0))
        except Exception:
            pass

    total = _decimal_value(employee, "base_salary")
    total += _decimal_value(employee, "housing_allowance")
    total += _decimal_value(employee, "transport_allowance")
    total += _decimal_value(employee, "other_allowance")
    total -= _decimal_value(employee, "deductions")
    return total


def _id_status(employee):
    try:
        return employee.id_status
    except Exception:
        return ""


@login_required
def employees(request):
    if not _can_access_accounting(request):
        return redirect("/workspace/")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = _employees_qs(request)
    field_names = {f.name for f in Employee._meta.fields}

    if status and "status" in field_names:
        qs = qs.filter(status=status)

    if q:
        search = Q()
        for field in ["full_name", "name", "national_id", "job_title", "phone", "email"]:
            if field in field_names:
                search |= Q(**{f"{field}__icontains": q})
        if search:
            qs = qs.filter(search)

    employees_list = list(qs)

    if "status" in field_names:
        active_count = qs.filter(status="active").count()
    else:
        active_count = len(employees_list)

    expired_count = sum(1 for e in employees_list if _id_status(e) == "expired")
    soon_count = sum(1 for e in employees_list if _id_status(e) == "soon")
    total_payroll = sum((_net_salary(e) for e in employees_list), Decimal("0"))

    return render(request, "accounting/employees.html", {
        "employees": employees_list,
        "q": q,
        "status": status,
        "active_count": active_count,
        "expired_count": expired_count,
        "soon_count": soon_count,
        "total_payroll": total_payroll,
    })
