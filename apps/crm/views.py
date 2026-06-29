from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.platform_core.models import Tenant, TenantMembership
from .forms import CompanyForm, ContactForm, DealForm, TaskForm
from .models import CRMCompany, CRMContact, CRMDeal, CRMTask, CRMQuote, CRMQuoteItem

def _default_tenant(user):
    if user.is_staff:
        return Tenant.objects.first()
    m = TenantMembership.objects.filter(user=user, is_active=True).select_related("tenant").first()
    return m.tenant if m else Tenant.objects.first()

def _tenant_ids(user):
    if user.is_staff:
        return None
    return list(TenantMembership.objects.filter(user=user, is_active=True).values_list("tenant_id", flat=True))

def _scope(qs, user):
    ids = _tenant_ids(user)
    return qs if ids is None else qs.filter(tenant_id__in=ids)

def _save(obj, request):
    if not obj.tenant_id:
        obj.tenant = _default_tenant(request.user)
    if hasattr(obj, "owner_id") and not obj.owner_id:
        obj.owner = request.user
    obj.save()
    return obj

@login_required
def dashboard(request):
    companies = _scope(CRMCompany.objects.all(), request.user)
    contacts = _scope(CRMContact.objects.all(), request.user)
    deals = _scope(CRMDeal.objects.all(), request.user)
    tasks = _scope(CRMTask.objects.all(), request.user)
    return render(request, "crm/dashboard.html", {
        "companies_count": companies.count(),
        "contacts_count": contacts.count(),
        "quotes_count": _scope(CRMQuote.objects.all(), request.user).count(),
        "quotes_pending": _scope(CRMQuote.objects.filter(status__in=["draft","sent"]), request.user).count(),
        "open_deals_count": deals.exclude(stage__in=["won","lost"]).count(),
        "won_value": deals.filter(stage="won").aggregate(total=Sum("value"))["total"] or 0,
        "open_tasks": tasks.filter(status="open")[:10],
    })

@login_required
def company_list(request):
    q = request.GET.get("q","").strip()
    qs = _scope(CRMCompany.objects.select_related("owner","tenant"), request.user)
    if q:
        qs = qs.filter(Q(name__icontains=q)|Q(email__icontains=q)|Q(phone__icontains=q))
    return render(request, "crm/company_list.html", {"companies": qs, "q": q})

@login_required
def company_create(request):
    form = CompanyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = _save(form.save(commit=False), request)
        messages.success(request, "تم إضافة العميل.")
        return redirect("crm:company_list")
    return render(request, "crm/form.html", {"form": form, "title": "إضافة عميل", "back_url": "crm:company_list"})


@login_required
def company_detail(request, pk):
    company = get_object_or_404(_scope(CRMCompany.objects.select_related("owner", "tenant"), request.user), pk=pk)
    # بناء Timeline مرتّب زمنياً
    timeline = []
    # عروض الأسعار
    for q in company.quotes.all():
        timeline.append({
            "type": "quote", "icon": "bi-file-earmark-text", "color": "#0b4ea2",
            "title": f"عرض سعر: {q.quote_number} - {q.title}",
            "sub": f"{q.total} {q.currency} | {q.get_status_display()}",
            "date": q.created_at, "url": f"/crm/quotes/{q.pk}/",
        })
    # المهام
    for t in company.tasks.all():
        timeline.append({
            "type": "task", "icon": "bi-check2-square", "color": "#d97706",
            "title": f"مهمة: {t.title}",
            "sub": f"{t.get_task_type_display()} | {t.get_status_display()}",
            "date": t.created_at, "url": None,
        })
    # الفرص
    for d in company.deals.all():
        timeline.append({
            "type": "deal", "icon": "bi-graph-up-arrow", "color": "#059669",
            "title": f"فرصة: {d.title}",
            "sub": f"{d.value} {d.currency} | {d.get_stage_display()}",
            "date": d.created_at, "url": f"/crm/deals/{d.pk}/",
        })
    # الفواتير الإلكترونية (قراءة فقط)
    try:
        from apps.payments.models import SalesInvoice
        email = company.email or ''
        if email:
            for inv in SalesInvoice.objects.filter(customer_email__iexact=email):
                timeline.append({
                    "type": "invoice", "icon": "bi-receipt", "color": "#7c3aed",
                    "title": f"فاتورة: {inv.invoice_number}",
                    "sub": f"{inv.total} {inv.currency.upper()} | {inv.get_status_display()}",
                    "date": inv.created_at, "url": f"/payments/sales-invoice/{inv.token}/",
                })
    except Exception:
        pass
    timeline.sort(key=lambda x: x["date"], reverse=True)
    return render(request, "crm/company_detail.html", {
        "company": company,
        "contacts": company.contacts.all(),
        "deals": company.deals.all(),
        "tasks": company.tasks.all(),
        "quotes": company.quotes.all(),
        "timeline": timeline,
    })


@login_required
def contact_detail(request, pk):
    contact = get_object_or_404(_scope(CRMContact.objects.select_related("company", "owner", "tenant"), request.user), pk=pk)
    return render(request, "crm/contact_detail.html", {
        "contact": contact,
        "deals": contact.deals.all(),
        "tasks": contact.tasks.all(),
    })


@login_required
def deal_detail(request, pk):
    deal = get_object_or_404(_scope(CRMDeal.objects.select_related("company", "contact", "owner", "tenant"), request.user), pk=pk)
    return render(request, "crm/deal_detail.html", {
        "deal": deal,
        "tasks": deal.tasks.all(),
    })


@login_required
def company_edit(request, pk):
    obj = get_object_or_404(_scope(CRMCompany.objects.all(), request.user), pk=pk)
    form = CompanyForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "تم التحديث.")
        return redirect("crm:company_list")
    return render(request, "crm/form.html", {"form": form, "title": "تعديل عميل", "back_url": "crm:company_list"})

@login_required
@require_POST
def company_delete(request, pk):
    get_object_or_404(_scope(CRMCompany.objects.all(), request.user), pk=pk).delete()
    messages.success(request, "تم حذف العميل.")
    return redirect("crm:company_list")

@login_required
def contact_list(request):
    q = request.GET.get("q","").strip()
    qs = _scope(CRMContact.objects.select_related("company","owner"), request.user)
    if q:
        qs = qs.filter(Q(full_name__icontains=q)|Q(email__icontains=q)|Q(phone__icontains=q))
    return render(request, "crm/contact_list.html", {"contacts": qs, "q": q})

@login_required
def contact_create(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        _save(form.save(commit=False), request); messages.success(request, "تم إضافة جهة الاتصال.")
        return redirect("crm:contact_list")
    return render(request, "crm/form.html", {"form": form, "title": "إضافة جهة اتصال", "back_url": "crm:contact_list"})

@login_required
def contact_edit(request, pk):
    obj = get_object_or_404(_scope(CRMContact.objects.all(), request.user), pk=pk)
    form = ContactForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "تم التحديث.")
        return redirect("crm:contact_list")
    return render(request, "crm/form.html", {"form": form, "title": "تعديل جهة اتصال", "back_url": "crm:contact_list"})

@login_required
@require_POST
def contact_delete(request, pk):
    get_object_or_404(_scope(CRMContact.objects.all(), request.user), pk=pk).delete()
    messages.success(request, "تم حذف جهة الاتصال.")
    return redirect("crm:contact_list")

@login_required
def deal_list(request):
    qs = _scope(CRMDeal.objects.select_related("company","contact","owner"), request.user)
    return render(request, "crm/deal_list.html", {"deals": qs})

@login_required
def deal_create(request):
    form = DealForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        _save(form.save(commit=False), request); messages.success(request, "تم إضافة الفرصة.")
        return redirect("crm:deal_list")
    return render(request, "crm/form.html", {"form": form, "title": "إضافة فرصة", "back_url": "crm:deal_list"})

@login_required
def deal_edit(request, pk):
    obj = get_object_or_404(_scope(CRMDeal.objects.all(), request.user), pk=pk)
    form = DealForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "تم التحديث.")
        return redirect("crm:deal_list")
    return render(request, "crm/form.html", {"form": form, "title": "تعديل فرصة", "back_url": "crm:deal_list"})

@login_required
@require_POST
def deal_delete(request, pk):
    get_object_or_404(_scope(CRMDeal.objects.all(), request.user), pk=pk).delete()
    messages.success(request, "تم حذف الفرصة.")
    return redirect("crm:deal_list")

@login_required
def task_list(request):
    qs = _scope(CRMTask.objects.select_related("company","contact","deal","assigned_to"), request.user)
    return render(request, "crm/task_list.html", {"tasks": qs})

@login_required
def task_create(request):
    form = TaskForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.tenant_id: obj.tenant = _default_tenant(request.user)
        if not obj.assigned_to_id: obj.assigned_to = request.user
        obj.save(); messages.success(request, "تم إضافة المهمة.")
        return redirect("crm:task_list")
    return render(request, "crm/form.html", {"form": form, "title": "إضافة مهمة", "back_url": "crm:task_list"})

@login_required
def task_edit(request, pk):
    obj = get_object_or_404(_scope(CRMTask.objects.all(), request.user), pk=pk)
    form = TaskForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "تم التحديث.")
        return redirect("crm:task_list")
    return render(request, "crm/form.html", {"form": form, "title": "تعديل مهمة", "back_url": "crm:task_list"})

@login_required
@require_POST
def task_done(request, pk):
    get_object_or_404(_scope(CRMTask.objects.all(), request.user), pk=pk).mark_done()
    messages.success(request, "تم إنجاز المهمة.")
    return redirect("crm:task_list")

@login_required
@require_POST
def task_delete(request, pk):
    get_object_or_404(_scope(CRMTask.objects.all(), request.user), pk=pk).delete()
    messages.success(request, "تم حذف المهمة.")
    return redirect("crm:task_list")

@login_required
def quote_list(request):
    return render(request, "crm/quote_list.html", {"quotes": [], "back_url": "/crm/"})


@login_required
def quote_create(request):
    messages.info(request, "سيتم تفعيل إنشاء عروض الأسعار في الخطوة التالية.")
    return redirect("crm:quote_list")


@login_required
def quote_detail(request, pk):
    messages.info(request, "تفاصيل عرض السعر ستُفعّل بعد إنشاء جدول عروض الأسعار.")
    return redirect("crm:quote_list")


@login_required
def quote_edit(request, pk):
    messages.info(request, "تعديل عرض السعر سيُفعّل بعد إنشاء جدول عروض الأسعار.")
    return redirect("crm:quote_list")


@login_required
@require_POST
def quote_delete(request, pk):
    messages.info(request, "حذف عرض السعر سيُفعّل بعد إنشاء جدول عروض الأسعار.")
    return redirect("crm:quote_list")


# ============ QUOTES ============

@login_required
def quote_list(request):
    from django.db.models import Q
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status', '')
    qs = _scope(CRMQuote.objects.select_related('company', 'contact', 'deal'), request.user)
    tid = _tenant_ids(request.user)
    if tid is not None:
        qs = qs.filter(tenant_id__in=tid)
    if q:
        qs = qs.filter(Q(quote_number__icontains=q) | Q(title__icontains=q) | Q(company__name__icontains=q))
    if status:
        qs = qs.filter(status=status)
    return render(request, 'crm/quote_list.html', {
        'quotes': qs, 'q': q, 'status': status,
        'status_choices': CRMQuote.STATUS_CHOICES,
    })


@login_required
def quote_create(request):
    companies = CRMCompany.objects.all()
    contacts = CRMContact.objects.all()
    deals = CRMDeal.objects.all()
    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        quote = CRMQuote.objects.create(
            tenant=_default_tenant(request.user),
            owner=request.user,
            title=request.POST.get('title', '').strip() or 'عرض سعر',
            status=request.POST.get('status', 'draft'),
            currency=request.POST.get('currency', 'AED'),
            notes=request.POST.get('notes', '').strip(),
            company_id=request.POST.get('company') or None,
            contact_id=request.POST.get('contact') or None,
            deal_id=request.POST.get('deal') or None,
        )
        try:
            quote.tax_rate = Decimal(request.POST.get('tax_rate') or '5')
        except InvalidOperation:
            quote.tax_rate = Decimal('5')
        if request.POST.get('valid_until'):
            quote.valid_until = request.POST.get('valid_until')
        quote.save()
        descs = request.POST.getlist('item_desc')
        qtys = request.POST.getlist('item_qty')
        prices = request.POST.getlist('item_price')
        for i, (d, qty, pr) in enumerate(zip(descs, qtys, prices)):
            d = (d or '').strip()
            if not d:
                continue
            try:
                qd = Decimal(qty or '1')
                pd = Decimal(pr or '0')
            except InvalidOperation:
                qd, pd = Decimal('1'), Decimal('0')
            CRMQuoteItem.objects.create(quote=quote, description=d, quantity=qd, unit_price=pd, order=i)
        quote.recalc()
        messages.success(request, f'تم إنشاء عرض السعر {quote.quote_number}')
        return redirect('crm:quote_detail', pk=quote.pk)
    return render(request, 'crm/quote_form.html', {
        'quote': None, 'companies': companies, 'contacts': contacts, 'deals': deals,
        'status_choices': CRMQuote.STATUS_CHOICES,
    })


@login_required
def quote_detail(request, pk):
    quote = get_object_or_404(_scope(CRMQuote.objects.prefetch_related('items'), request.user), pk=pk)
    from apps.payments.models import CompanySettings
    company = CompanySettings.load()
    return render(request, 'crm/quote_detail.html', {
        'quote': quote, 'company': company, 'qr_data_uri': '',
    })


@login_required
def quote_edit(request, pk):
    quote = get_object_or_404(_scope(CRMQuote.objects.prefetch_related('items'), request.user), pk=pk)
    companies = CRMCompany.objects.all()
    contacts = CRMContact.objects.all()
    deals = CRMDeal.objects.all()
    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        quote.title = request.POST.get('title', '').strip() or quote.title
        quote.status = request.POST.get('status', quote.status)
        quote.currency = request.POST.get('currency', quote.currency)
        quote.notes = request.POST.get('notes', '').strip()
        quote.company_id = request.POST.get('company') or None
        quote.contact_id = request.POST.get('contact') or None
        quote.deal_id = request.POST.get('deal') or None
        try:
            quote.tax_rate = Decimal(request.POST.get('tax_rate') or '5')
        except InvalidOperation:
            pass
        quote.valid_until = request.POST.get('valid_until') or None
        quote.save()
        quote.items.all().delete()
        descs = request.POST.getlist('item_desc')
        qtys = request.POST.getlist('item_qty')
        prices = request.POST.getlist('item_price')
        for i, (d, qty, pr) in enumerate(zip(descs, qtys, prices)):
            d = (d or '').strip()
            if not d:
                continue
            try:
                qd = Decimal(qty or '1')
                pd = Decimal(pr or '0')
            except InvalidOperation:
                qd, pd = Decimal('1'), Decimal('0')
            CRMQuoteItem.objects.create(quote=quote, description=d, quantity=qd, unit_price=pd, order=i)
        quote.recalc()
        messages.success(request, 'تم حفظ التعديلات')
        return redirect('crm:quote_detail', pk=quote.pk)
    return render(request, 'crm/quote_form.html', {
        'quote': quote, 'companies': companies, 'contacts': contacts, 'deals': deals,
        'status_choices': CRMQuote.STATUS_CHOICES,
    })


@login_required
@require_POST
def quote_delete(request, pk):
    quote = get_object_or_404(CRMQuote, pk=pk)
    quote.delete()
    messages.success(request, 'تم حذف عرض السعر')
    return redirect('crm:quote_list')


@login_required
def quote_pdf(request, pk):
    quote = get_object_or_404(_scope(CRMQuote.objects.prefetch_related('items'), request.user), pk=pk)
    from apps.payments.models import CompanySettings
    company = CompanySettings.load()
    qr_data_uri = ''
    try:
        import qrcode, io, base64
        url = request.build_absolute_uri()
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_data_uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    html = render_to_string('crm/quote_detail.html', {
        'quote': quote, 'company': company, 'qr_data_uri': qr_data_uri, 'pdf_mode': True,
    })
    try:
        from weasyprint import HTML
        pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{quote.quote_number}.pdf"'
        return resp
    except Exception as e:
        return HttpResponse(f'تعذّر توليد PDF: {e}', status=500)


@login_required
@require_POST
def quote_to_invoice(request, pk):
    from decimal import Decimal, InvalidOperation
    from apps.payments.models import SalesInvoice, SalesInvoiceItem
    quote = get_object_or_404(_scope(CRMQuote.objects.prefetch_related('items'), request.user), pk=pk)
    inv = SalesInvoice.objects.create(
        kind='sales',
        customer_name=quote.company.name if quote.company else (quote.contact.full_name if quote.contact else quote.title),
        customer_email=quote.contact.email if quote.contact else '',
        customer_phone=quote.contact.phone if quote.contact else '',
        payment_method='bank',
        status='unpaid',
        currency=quote.currency.lower(),
        tax_rate=quote.tax_rate,
        notes=quote.notes,
    )
    for i, item in enumerate(quote.items.all()):
        SalesInvoiceItem.objects.create(
            invoice=inv,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            order=i,
        )
    quote.status = 'accepted'
    quote.save(update_fields=['status'])
    messages.success(request, f'تم إنشاء الفاتورة {inv.invoice_number} من عرض السعر {quote.quote_number}')
    return redirect('payments:sales_invoice_print', token=inv.token)


@login_required
@require_POST
def quote_send_email(request, pk):
    quote = get_object_or_404(_scope(CRMQuote.objects.prefetch_related('items'), request.user), pk=pk)
    from .services import send_quote_email
    success, msg = send_quote_email(quote, request)
    if success:
        messages.success(request, msg)
    else:
        messages.error(request, f'فشل الإرسال: {msg}')
    return redirect('crm:quote_detail', pk=pk)
