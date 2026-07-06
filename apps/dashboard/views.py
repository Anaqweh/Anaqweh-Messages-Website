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


# ── الاشتراكات ──
@login_required
@user_passes_test(_is_admin)
def subscriptions(request):
    from apps.platform_core.models import SubscriptionPlan, TenantSubscription, Tenant
    from django.utils import timezone
    today = timezone.localdate()
    subs = TenantSubscription.objects.select_related("tenant", "plan").order_by("end_date")
    plans = SubscriptionPlan.objects.all()
    # شركات بلا اشتراك (لعرضها للربط)
    linked_ids = subs.values_list("tenant_id", flat=True)
    unlinked = Tenant.objects.exclude(id__in=linked_ids).order_by("name")
    # إحصاءات
    expiring = [s for s in subs if s.status == "active" and 0 <= s.days_left <= 7]
    expired = [s for s in subs if s.status == "active" and s.is_expired]
    monthly_revenue = sum((s.plan.price_monthly for s in subs if s.status == "active" and s.plan and not s.is_expired), 0)
    return render(request, "dashboard/subscriptions.html", {
        "subs": subs, "plans": plans, "unlinked": unlinked,
        "expiring": expiring, "expired": expired,
        "monthly_revenue": monthly_revenue, "today": today,
        "active": "subscriptions",
    })


@login_required
@user_passes_test(_is_admin)
def plan_add(request):
    from apps.platform_core.models import SubscriptionPlan
    from django.shortcuts import redirect
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        price = (request.POST.get("price") or "0").strip()
        desc = (request.POST.get("description") or "").strip()
        if name:
            SubscriptionPlan.objects.create(name=name, price_monthly=price or 0, description=desc)
    return redirect("dashboard:subscriptions")


@login_required
@user_passes_test(_is_admin)
def subscription_save(request):
    """ربط/تحديث اشتراك شركة بباقة وتواريخ."""
    from apps.platform_core.models import SubscriptionPlan, TenantSubscription, Tenant
    from django.shortcuts import redirect
    if request.method == "POST":
        tenant_id = request.POST.get("tenant")
        plan_id = request.POST.get("plan")
        start = request.POST.get("start_date")
        end = request.POST.get("end_date")
        status = request.POST.get("status", "active")
        if tenant_id and start and end:
            tenant = Tenant.objects.filter(pk=tenant_id).first()
            plan = SubscriptionPlan.objects.filter(pk=plan_id).first() if plan_id else None
            if tenant:
                TenantSubscription.objects.update_or_create(
                    tenant=tenant,
                    defaults={"plan": plan, "start_date": start, "end_date": end, "status": status},
                )
    return redirect("dashboard:subscriptions")
