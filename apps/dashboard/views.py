from django.http import HttpResponseForbidden
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
            SubscriptionPlan.objects.create(
                name=name, price_monthly=price or 0, description=desc,
                features=(request.POST.get("features") or "").strip(),
                is_featured=bool(request.POST.get("is_featured")),
                show_on_landing=bool(request.POST.get("show_on_landing")),
            )
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








@login_required
def landing_page_admin(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Forbidden")
    from apps.platform_core.models import LandingContent
    obj = LandingContent.get_solo()
    fields = ["hero_badge","hero_title","hero_desc","features_title","services_title",
              "pricing_title","pricing_sub","pillar1_title","pillar1_desc",
              "pillar2_title","pillar2_desc","footer_company","footer_tagline","footer_location","whatsapp_phone","privacy_content","terms_content"]
    from apps.platform_core.models import SubscriptionPlan
    saved = False
    if request.method == "POST":
        action = request.POST.get("action", "content")
        if action == "content":
            for f in fields:
                setattr(obj, f, (request.POST.get(f) or "").strip())
            if request.FILES.get("parent_logo"):
                obj.parent_logo = request.FILES["parent_logo"]
            obj.show_parent_logo = bool(request.POST.get("show_parent_logo"))
            obj.save()
            saved = True
        elif action == "plan_add":
            name = (request.POST.get("p_name") or "").strip()
            if name:
                SubscriptionPlan.objects.create(
                    name=name,
                    price_monthly=(request.POST.get("p_price") or "0").strip() or 0,
                    price_yearly=(request.POST.get("p_price_yearly") or "0").strip() or 0,
                    currency=(request.POST.get("p_currency") or "AED").strip() or "AED",
                    description=(request.POST.get("p_desc") or "").strip(),
                    features=(request.POST.get("p_features") or "").strip(),
                    is_featured=bool(request.POST.get("p_featured")),
                    show_on_landing=bool(request.POST.get("p_landing")),
                )
            saved = True
        elif action == "plan_edit":
            p = SubscriptionPlan.objects.filter(pk=request.POST.get("plan_id")).first()
            if p:
                p.name = (request.POST.get("p_name") or p.name).strip()
                p.price_monthly = (request.POST.get("p_price") or "0").strip() or 0
                p.price_yearly = (request.POST.get("p_price_yearly") or "0").strip() or 0
                p.currency = (request.POST.get("p_currency") or "AED").strip() or "AED"
                p.description = (request.POST.get("p_desc") or "").strip()
                p.features = (request.POST.get("p_features") or "").strip()
                p.is_featured = bool(request.POST.get("p_featured"))
                p.show_on_landing = bool(request.POST.get("p_landing"))
                p.save()
            saved = True
        elif action == "plan_delete":
            SubscriptionPlan.objects.filter(pk=request.POST.get("plan_id")).delete()
            saved = True
        elif action == "client_add":
            from apps.platform_core.models import LandingClient
            cname = (request.POST.get("c_name") or "").strip()
            if cname:
                LandingClient.objects.create(name=cname, icon=(request.POST.get("c_icon") or "bi-building").strip(), is_featured=bool(request.POST.get("c_featured")))
            saved = True
        elif action == "client_delete":
            from apps.platform_core.models import LandingClient
            LandingClient.objects.filter(pk=request.POST.get("client_id")).delete()
            saved = True
    plans = SubscriptionPlan.objects.all().order_by("sort_order", "price_monthly")
    from apps.platform_core.models import LandingClient
    clients = LandingClient.objects.all()
    return render(request, "dashboard/landing_page.html", {
        "public_url": "https://inexcsuite.com/landing/",
        "lc": obj, "saved": saved, "plans": plans, "clients": clients,
    })


from django.contrib.auth.decorators import login_required as _landing_demo_login_required


def _landing_demo_admin_allowed(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    try:
        from apps.platform_core.navigation import is_platform_admin
        return bool(is_platform_admin(user))
    except Exception:
        return False


@_landing_demo_login_required
def landing_demo_requests(request):
    from django.http import HttpResponseForbidden
    from django.shortcuts import get_object_or_404, redirect, render
    import re
    from apps.platform_core.models import LandingDemoRequest

    if not _landing_demo_admin_allowed(request.user):
        return HttpResponseForbidden("Forbidden")

    if request.method == "POST":
        lead = get_object_or_404(LandingDemoRequest, pk=request.POST.get("lead_id"))
        status = request.POST.get("status")
        allowed = dict(LandingDemoRequest.STATUS_CHOICES)
        if status in allowed:
            lead.status = status
            lead.save(update_fields=["status", "updated_at"])
        return redirect("dashboard:landing_demo_requests")

    qs = LandingDemoRequest.objects.all()
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)

    leads = list(qs[:200])
    for lead in leads:
        digits = re.sub(r"\\D+", "", lead.phone or "")
        if digits.startswith("00"):
            digits = digits[2:]
        if digits.startswith("0"):
            digits = "971" + digits[1:]
        lead.whatsapp_url = ("https://wa.me/" + digits) if digits else ""

    context = {
        "leads": leads,
        "status_filter": status,
        "status_choices": LandingDemoRequest.STATUS_CHOICES,
        "total_count": LandingDemoRequest.objects.count(),
        "new_count": LandingDemoRequest.objects.filter(status="new").count(),
    }
    return render(request, "dashboard/landing_demo_requests.html", context)

def subscription_renew(request, pk):
    """تجديد سريع: +30 يوم من الأبعد بين اليوم وتاريخ النهاية الحالي."""
    from apps.platform_core.models import TenantSubscription
    from django.shortcuts import redirect
    from django.utils import timezone
    import datetime
    sub = TenantSubscription.objects.filter(pk=pk).first()
    if sub and request.method == "POST":
        base = max(sub.end_date, timezone.now().date())
        sub.end_date = base + datetime.timedelta(days=30)
        sub.status = "active"
        sub.save()
    return redirect("dashboard:subscriptions")


def subscription_toggle(request, pk):
    """تبديل الحالة نشط/موقوف."""
    from apps.platform_core.models import TenantSubscription
    from django.shortcuts import redirect
    sub = TenantSubscription.objects.filter(pk=pk).first()
    if sub and request.method == "POST":
        sub.status = "suspended" if sub.status == "active" else "active"
        sub.save()
    return redirect("dashboard:subscriptions")

def dismiss_onboarding(request):
    from django.shortcuts import redirect
    from apps.platform_core.navigation import active_membership_for
    if request.method == "POST":
        m = active_membership_for(request.user)
        if m:
            m.onboarding_seen = True
            m.save()
    return redirect(request.POST.get("next") or "dashboard:home")

def global_search(request):
    from django.http import JsonResponse
    import re as _re
    if not request.user.is_authenticated:
        return JsonResponse({"results": []})
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    def _norm(p):
        d = _re.sub("[^0-9]", "", p or "")
        if d.startswith("00"): d = d[2:]
        for cc in ("971", "962", "966", "965", "968", "974", "973", "20"):
            if d.startswith(cc) and len(d) > len(cc) + 6:
                d = d[len(cc):]
                break
        return d.lstrip("0")

    def _ar(s):
        s = (s or "").lower()
        for a, b in (("\u0623","\u0627"),("\u0625","\u0627"),("\u0622","\u0627"),("\u0629","\u0647"),("\u0649","\u064a")):
            s = s.replace(a, b)
        return s

    nq = _norm(q)
    is_num = len(nq) >= 4
    toks = []
    for t in _ar(q).split():
        if t.startswith("\u0627\u0644") and len(t) > 3:
            t = t[2:]
        toks.append(t)

    def _match(name, phone):
        nn = _ar(name)
        if toks and all(t in nn for t in toks):
            return True
        if is_num:
            np = _norm(phone)
            return bool(np) and (nq in np or np in nq)
        return False

    from apps.platform_core.navigation import active_membership_for
    m = active_membership_for(request.user)
    _t = m.tenant if m else None
    results = []
    try:
        from apps.registrations.models import RegClient
        qs = RegClient.objects.filter(tenant=_t) if _t else RegClient.objects.filter(tenant__isnull=True)
        for r in qs:
            if _match(r.name, r.phone):
                results.append({"type": "\u0639\u0645\u0644\u0627\u0621 \u0627\u0644\u0645\u062a\u0627\u0628\u0639\u0629", "color": "#4f46e5", "name": r.name, "sub": r.phone, "url": "/registrations/clients/?edit=%d#clForm" % r.pk})
                if len(results) >= 15: break
    except Exception:
        pass
    try:
        from apps.crm.models import CRMContact, CRMCompany
        qs = CRMContact.objects.filter(tenant=_t) if _t else CRMContact.objects.filter(tenant__isnull=True)
        for r in qs:
            if _match(r.full_name, r.phone):
                results.append({"type": "\u062c\u0647\u0627\u062a \u0627\u062a\u0635\u0627\u0644 CRM", "color": "#0f9d58", "name": r.full_name, "sub": r.phone or "", "url": "/crm/contacts/"})
                if len(results) >= 15: break
        qs2 = CRMCompany.objects.filter(tenant=_t) if _t else CRMCompany.objects.filter(tenant__isnull=True)
        for r in qs2:
            if _match(r.name, r.phone):
                results.append({"type": "\u0634\u0631\u0643\u0627\u062a CRM", "color": "#b45309", "name": r.name, "sub": r.phone or "", "url": "/crm/companies/"})
                if len(results) >= 15: break
    except Exception:
        pass
    return JsonResponse({"results": results[:15]})
