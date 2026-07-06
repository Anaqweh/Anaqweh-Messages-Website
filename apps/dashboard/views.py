from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test


def _is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def _paginate(request, qs, per=25):
    from django.core.paginator import Paginator
    page = request.GET.get("page", 1)
    return Paginator(qs, per).get_page(page)


@login_required
@user_passes_test(_is_admin)
def dashboard_home(request):
    stats = {}
    try:
        from apps.platform_core.models import Tenant, PlatformAuditLog
        stats["companies"] = Tenant.objects.count()
        stats["recent_logs"] = PlatformAuditLog.objects.order_by("-id")[:8]
    except Exception:
        stats["companies"] = 0
        stats["recent_logs"] = []
    try:
        from apps.crm.models import CRMCompany, CRMContact, CRMQuote, CRMDeal
        stats["customers"] = CRMCompany.objects.count() + CRMContact.objects.count()
        stats["quotes"] = CRMQuote.objects.count()
        stats["deals"] = CRMDeal.objects.count()
    except Exception:
        stats["customers"] = stats["quotes"] = stats["deals"] = 0
    try:
        from apps.registrations.models import RegistrationSubmission
        stats["registrations"] = RegistrationSubmission.objects.count()
    except Exception:
        stats["registrations"] = 0
    try:
        from apps.payments.models import Payment, Invoice
        stats["payments"] = Payment.objects.count()
        stats["invoices"] = Invoice.objects.count()
    except Exception:
        stats["payments"] = stats["invoices"] = 0
    # بيانات الرسوم البيانية (قراءة فقط)
    charts = {"quote_status": {"labels": [], "data": []}, "monthly": {"labels": [], "data": []}}
    try:
        from apps.crm.models import CRMQuote
        from django.db.models import Count
        status_map = {"draft": "مسودة", "sent": "مُرسل", "accepted": "مقبول", "rejected": "مرفوض", "expired": "منتهي"}
        rows = CRMQuote.objects.values("status").annotate(c=Count("id")).order_by("-c")
        for r in rows:
            charts["quote_status"]["labels"].append(status_map.get(r["status"], r["status"] or "غير محدد"))
            charts["quote_status"]["data"].append(r["c"])
    except Exception:
        pass
    try:
        from apps.registrations.models import RegistrationSubmission
        from django.db.models.functions import TruncMonth
        from django.db.models import Count
        rows = (RegistrationSubmission.objects
                .annotate(m=TruncMonth("created_at"))
                .values("m").annotate(c=Count("id")).order_by("m"))[:12]
        for r in rows:
            if r["m"]:
                charts["monthly"]["labels"].append(r["m"].strftime("%Y-%m"))
                charts["monthly"]["data"].append(r["c"])
    except Exception:
        pass
    import json
    return render(request, "dashboard/index.html", {
        "stats": stats, "active": "home",
        "charts_json": json.dumps(charts, ensure_ascii=False),
    })


@login_required
@user_passes_test(_is_admin)
def companies(request):
    from apps.platform_core.models import Tenant
    q = request.GET.get("q", "").strip()
    qs = Tenant.objects.all().order_by("-id")
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, "dashboard/companies.html", {"page_obj": _paginate(request, qs), "q": q, "active": "companies"})


@login_required
@user_passes_test(_is_admin)
def customers(request):
    from apps.crm.models import CRMContact
    q = request.GET.get("q", "").strip()
    qs = CRMContact.objects.select_related("company", "tenant").order_by("-id")
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q))
    return render(request, "dashboard/customers.html", {"page_obj": _paginate(request, qs), "q": q, "active": "customers"})


@login_required
@user_passes_test(_is_admin)
def registrations(request):
    from apps.registrations.models import RegistrationSubmission
    q = request.GET.get("q", "").strip()
    qs = RegistrationSubmission.objects.order_by("-id")
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(student_name__icontains=q) | Q(student_email__icontains=q))
    return render(request, "dashboard/registrations.html", {"page_obj": _paginate(request, qs), "q": q, "active": "registrations"})


@login_required
@user_passes_test(_is_admin)
def payments(request):
    from apps.payments.models import Payment
    qs = Payment.objects.order_by("-id")
    return render(request, "dashboard/payments.html", {"page_obj": _paginate(request, qs), "active": "payments"})


# ── CRUD العملاء (CRMContact) — محمي بالمدير ──
_CONTACT_FIELDS = ["full_name", "job_title", "email", "phone", "whatsapp", "source", "notes"]


def _contact_data(request):
    return {f: (request.POST.get(f, "") or "").strip() for f in _CONTACT_FIELDS}


@login_required
@user_passes_test(_is_admin)
def customer_add(request):
    from apps.crm.models import CRMContact
    error = ""
    data = {f: "" for f in _CONTACT_FIELDS}
    if request.method == "POST":
        data = _contact_data(request)
        if not data["full_name"]:
            error = "الاسم مطلوب"
        else:
            CRMContact.objects.create(**data)
            from django.shortcuts import redirect
            return redirect("dashboard:customers")
    return render(request, "dashboard/customer_form.html",
                  {"data": data, "error": error, "mode": "add", "active": "customers"})


@login_required
@user_passes_test(_is_admin)
def customer_edit(request, pk):
    from apps.crm.models import CRMContact
    from django.shortcuts import get_object_or_404, redirect
    obj = get_object_or_404(CRMContact, pk=pk)
    error = ""
    if request.method == "POST":
        data = _contact_data(request)
        if not data["full_name"]:
            error = "الاسم مطلوب"
        else:
            for f in _CONTACT_FIELDS:
                setattr(obj, f, data[f])
            obj.save()
            return redirect("dashboard:customers")
    data = {f: getattr(obj, f, "") for f in _CONTACT_FIELDS}
    return render(request, "dashboard/customer_form.html",
                  {"data": data, "error": error, "mode": "edit", "obj": obj, "active": "customers"})


@login_required
@user_passes_test(_is_admin)
def customer_delete(request, pk):
    from apps.crm.models import CRMContact
    from django.shortcuts import get_object_or_404, redirect
    obj = get_object_or_404(CRMContact, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("dashboard:customers")
    return render(request, "dashboard/customer_delete.html",
                  {"obj": obj, "active": "customers"})
