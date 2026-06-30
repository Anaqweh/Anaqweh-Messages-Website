from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from .models import CRMCompany, CRMContact, CRMDeal, CRMQuote
from .tenant_scope import assign_crm_tenant, crm_scope_queryset


def _field_names(model):
    return {f.name for f in model._meta.fields}


def _decimal(value, default="0"):
    try:
        return Decimal(str(value or default))
    except Exception:
        return Decimal(default)


def _choices(request):
    return {
        "companies": crm_scope_queryset(request, CRMCompany),
        "contacts": crm_scope_queryset(request, CRMContact),
        "deals": crm_scope_queryset(request, CRMDeal),
    }


def _set_fk(request, obj, field_name, model):
    names = _field_names(CRMQuote)
    if field_name not in names:
        return

    raw = request.POST.get(field_name)
    if not raw:
        setattr(obj, field_name, None)
        return

    related = get_object_or_404(crm_scope_queryset(request, model), pk=raw)
    setattr(obj, field_name, related)


def _save_quote_from_post(request, quote=None):
    names = _field_names(CRMQuote)
    quote = quote or CRMQuote()

    if "title" in names:
        quote.title = (request.POST.get("title") or "").strip() or "عرض سعر"

    if "customer_email" in names:
        quote.customer_email = (request.POST.get("customer_email") or "").strip()

    if "status" in names:
        quote.status = request.POST.get("status") or getattr(quote, "status", "draft") or "draft"

    if "currency" in names:
        quote.currency = (request.POST.get("currency") or "AED").strip().upper()

    if "tax_rate" in names:
        quote.tax_rate = _decimal(request.POST.get("tax_rate"), "5")

    if "subtotal" in names:
        quote.subtotal = _decimal(request.POST.get("subtotal"), "0")

    if "tax_amount" in names:
        subtotal = _decimal(request.POST.get("subtotal"), "0")
        tax_rate = _decimal(request.POST.get("tax_rate"), "5")
        quote.tax_amount = _decimal(request.POST.get("tax_amount"), str((subtotal * tax_rate) / Decimal("100")))

    if "total" in names:
        subtotal = _decimal(request.POST.get("subtotal"), "0")
        tax_amount = getattr(quote, "tax_amount", Decimal("0")) or Decimal("0")
        quote.total = _decimal(request.POST.get("total"), str(subtotal + tax_amount))

    if "valid_until" in names:
        quote.valid_until = parse_date(request.POST.get("valid_until") or "") or None

    if "notes" in names:
        quote.notes = request.POST.get("notes") or ""

    _set_fk(request, quote, "company", CRMCompany)
    _set_fk(request, quote, "contact", CRMContact)
    _set_fk(request, quote, "deal", CRMDeal)

    assign_crm_tenant(request, quote)
    quote.save()
    return quote


@login_required
def quote_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = crm_scope_queryset(request, CRMQuote)

    for rel in ["company", "contact", "deal", "owner"]:
        try:
            qs = qs.select_related(rel)
        except Exception:
            pass

    if q:
        from django.db.models import Q
        search = Q()
        names = _field_names(CRMQuote)
        for field in ["title", "quote_number", "status", "currency"]:
            if field in names:
                search |= Q(**{f"{field}__icontains": q})
        if search:
            qs = qs.filter(search)

    return render(request, "crm/quotes_secure/list.html", {
        "quotes": qs,
        "q": q,
    })


@login_required
def quote_create(request):
    if request.method == "POST":
        quote = _save_quote_from_post(request)
        messages.success(request, "تم إنشاء عرض السعر داخل مساحة الشركة فقط.")
        return redirect(f"/crm/quotes/{quote.pk}/")

    return render(request, "crm/quotes_secure/form.html", {
        "quote": None,
        **_choices(request),
    })


@login_required
def quote_detail(request, pk):
    quote = get_object_or_404(crm_scope_queryset(request, CRMQuote), pk=pk)
    return render(request, "crm/quotes_secure/detail.html", {"quote": quote})


@login_required
def quote_edit(request, pk):
    quote = get_object_or_404(crm_scope_queryset(request, CRMQuote), pk=pk)

    if request.method == "POST":
        quote = _save_quote_from_post(request, quote)
        messages.success(request, "تم تحديث عرض السعر داخل مساحة الشركة فقط.")
        return redirect(f"/crm/quotes/{quote.pk}/")

    return render(request, "crm/quotes_secure/form.html", {
        "quote": quote,
        **_choices(request),
    })


@login_required
def quote_delete(request, pk):
    quote = get_object_or_404(crm_scope_queryset(request, CRMQuote), pk=pk)

    if request.method == "POST":
        quote.delete()
        messages.success(request, "تم حذف عرض السعر.")
        return redirect("/crm/quotes/")

    return render(request, "crm/quotes_secure/delete.html", {"quote": quote})


# INEXC_SECURE_QUOTE_ACTIONS
def _assert_quote_access(request, pk):
    return get_object_or_404(crm_scope_queryset(request, CRMQuote), pk=pk)


@login_required
def quote_print(request, pk):
    _assert_quote_access(request, pk)
    from . import views as legacy_views
    return legacy_views.quote_print(request, pk)


@login_required
def quote_pdf(request, pk):
    _assert_quote_access(request, pk)
    from . import views as legacy_views
    return legacy_views.quote_pdf(request, pk)


@login_required
def quote_to_invoice(request, pk):
    _assert_quote_access(request, pk)
    from . import views as legacy_views
    return legacy_views.quote_to_invoice(request, pk)


@login_required
def quote_send_email(request, pk):
    quote = _assert_quote_access(request, pk)

    posted_email = (
        request.POST.get("customer_email")
        or request.POST.get("email")
        or ""
    ).strip()

    if posted_email and hasattr(quote, "customer_email"):
        quote.customer_email = posted_email
        quote.save(update_fields=["customer_email"])

    email = (getattr(quote, "customer_email", "") or "").strip()

    if not email:
        for obj in [getattr(quote, "contact", None), getattr(quote, "company", None)]:
            candidate = (getattr(obj, "email", "") or "").strip() if obj else ""
            if candidate:
                email = candidate
                if hasattr(quote, "customer_email"):
                    quote.customer_email = email
                    quote.save(update_fields=["customer_email"])
                break

    if not email:
        messages.error(request, "فشل الإرسال: أدخل بريد العميل أولاً ثم أعد الإرسال.")
        return redirect(f"/crm/quotes/{quote.pk}/")

    from . import views as legacy_views
    request.POST = request.POST.copy()
    request.POST["email"] = email
    request.POST["customer_email"] = email
    return legacy_views.quote_send_email(request, pk)

# INEXC_FINAL_SECURE_QUOTE_CONTEXT_VIEWS
@login_required
def quote_list(request):
    from django.shortcuts import redirect
    from .tenant_scope import apply_crm_admin_context, quote_context_data

    if apply_crm_admin_context(request):
        return redirect("/crm/quotes/")

    q = (request.GET.get("q") or "").strip()
    qs = crm_scope_queryset(request, CRMQuote)

    for rel in ["company", "contact", "deal", "owner"]:
        try:
            qs = qs.select_related(rel)
        except Exception:
            pass

    if q:
        from django.db.models import Q
        search = Q()
        names = _field_names(CRMQuote)
        for field in ["title", "quote_number", "status", "currency"]:
            if field in names:
                search |= Q(**{f"{field}__icontains": q})
        if search:
            qs = qs.filter(search)

    context = {
        "quotes": qs,
        "q": q,
    }
    context.update(quote_context_data(request))

    return render(request, "crm/quotes_secure/list.html", context)


@login_required
def quote_to_invoice(request, pk):
    quote = _assert_quote_access(request, pk)

    from . import views as legacy_views
    response = legacy_views.quote_to_invoice(request, pk)

    # إذا أنشأ التحويل فاتورة، اربطها بنفس tenant الخاص بعرض السعر.
    try:
        import re
        from apps.payments.models import SalesInvoice

        location = response.get("Location", "") or ""
        token_match = re.search(r"/sales-invoice/([^/]+)/", location)
        if token_match:
            token = token_match.group(1)
            invoice = SalesInvoice.objects.filter(token=token).first()
            if invoice and hasattr(invoice, "tenant_id"):
                invoice.tenant = quote.tenant
                invoice.save(update_fields=["tenant"])
    except Exception:
        pass

    return response


# INEXC_DIRECT_QUOTE_EMAIL_SEND_PATCH
@login_required
def quote_send_email(request, pk):
    import time
    from django.conf import settings
    from django.contrib import messages
    from django.core.mail import EmailMessage, get_connection
    from django.shortcuts import redirect, get_object_or_404
    from django.utils.html import escape

    quote = get_object_or_404(crm_scope_queryset(request, CRMQuote), pk=pk)

    posted_email = ""
    if request.method == "POST":
        posted_email = (
            request.POST.get("customer_email")
            or request.POST.get("email")
            or request.POST.get("to_email")
            or ""
        ).strip()

    saved_email = (getattr(quote, "customer_email", "") or "").strip()
    contact_email = (getattr(getattr(quote, "contact", None), "email", "") or "").strip()
    company_email = (getattr(getattr(quote, "company", None), "email", "") or "").strip()
    email = posted_email or saved_email or contact_email or company_email

    if posted_email and hasattr(quote, "customer_email"):
        quote.customer_email = posted_email
        fields = ["customer_email"]
        if hasattr(quote, "updated_at"):
            fields.append("updated_at")
        quote.save(update_fields=fields)

    if not email:
        messages.error(request, "فشل الإرسال: أدخل بريد العميل أولاً ثم اضغط إرسال.")
        return redirect(f"/crm/quotes/{quote.pk}/#send-email-section")

    quote_number = escape(getattr(quote, "quote_number", "") or f"QUOTE-{quote.pk}")
    title = escape(getattr(quote, "title", "") or "عرض سعر")
    total = escape(str(getattr(quote, "total", "") or ""))
    currency = escape(getattr(quote, "currency", "") or "AED")
    customer = escape(str(
        getattr(quote, "customer_name", "")
        or getattr(getattr(quote, "contact", None), "name", "")
        or getattr(getattr(quote, "company", None), "name", "")
        or "-"
    ))

    html_body = f"""
    <div dir="rtl" style="font-family:Arial,sans-serif;line-height:1.8">
      <h2 style="color:#0b4ea2">عرض سعر {quote_number}</h2>
      <p>مرحباً،</p>
      <p>مرفق/مذكور لكم عرض السعر التالي:</p>
      <table style="border-collapse:collapse;width:100%;max-width:650px">
        <tr><td style="border:1px solid #d9e4f2;padding:8px"><b>العنوان</b></td><td style="border:1px solid #d9e4f2;padding:8px">{title}</td></tr>
        <tr><td style="border:1px solid #d9e4f2;padding:8px"><b>العميل</b></td><td style="border:1px solid #d9e4f2;padding:8px">{customer}</td></tr>
        <tr><td style="border:1px solid #d9e4f2;padding:8px"><b>الإجمالي</b></td><td style="border:1px solid #d9e4f2;padding:8px">{total} {currency}</td></tr>
      </table>
      <p>مع التحية.</p>
    </div>
    """

    subject = f"عرض سعر {quote_number}"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None) or "info@inexc.com"

    started = time.time()
    try:
        import socket

        original_getaddrinfo = socket.getaddrinfo

        def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            results = original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            return results

        socket.getaddrinfo = ipv4_only_getaddrinfo
        try:
            connection = get_connection(timeout=12, fail_silently=False)
            message = EmailMessage(
                subject=subject,
                body=html_body,
                from_email=from_email,
                to=[email],
                connection=connection,
            )
            message.content_subtype = "html"

            # لا نولّد PDF هنا حتى لا يعلق الطلب. PDF يبقى من زر تنزيل PDF.
            sent = message.send(fail_silently=False)
        finally:
            socket.getaddrinfo = original_getaddrinfo

        elapsed = round(time.time() - started, 2)
        if sent:
            messages.success(request, f"تم إرسال عرض السعر إلى {email} بنجاح خلال {elapsed} ثانية.")
        else:
            messages.error(request, "لم يتم الإرسال: خادم البريد لم يؤكد إرسال الرسالة.")
    except Exception as exc:
        messages.error(request, f"فشل الإرسال عبر البريد: {exc}")

    return redirect(f"/crm/quotes/{quote.pk}/")



# INEXC_EMAILJS_QUOTE_SEND_FINAL
from django.contrib.auth.decorators import login_required as _inexc_quote_login_required

def _inexc_get_emailjs_config(request=None):
    from django.apps import apps
    from django.contrib.auth import get_user_model

    def clean(value):
        return (value or "").strip()

    def cfg_from_obj(obj):
        if not obj:
            return None

        service_id = clean(getattr(obj, "service_id", ""))
        template_id = clean(getattr(obj, "template_id", ""))
        public_key = clean(getattr(obj, "public_key", ""))
        private_key = clean(getattr(obj, "private_key", ""))

        if not service_id or not template_id or not public_key:
            return None

        return {
            "service_id": service_id,
            "template_id": template_id,
            "public_key": public_key,
            "private_key": private_key,
            "sender_name": clean(getattr(obj, "from_name", "")) or clean(getattr(obj, "sender_name", "")) or "INEXC",
            "sender_email": clean(getattr(obj, "from_email", "")) or clean(getattr(obj, "sender_email", "")) or "info@inexc.com",
            "source": f"db:{getattr(getattr(obj, 'user', None), 'username', 'unknown')}",
        }

    try:
        Config = apps.get_model("accounts", "UserEmailJSConfig")
    except Exception:
        return {}

    user = getattr(request, "user", None) if request else None

    # 1) إعدادات المستخدم الحالي أولاً
    if user and getattr(user, "is_authenticated", False):
        cfg = cfg_from_obj(Config.objects.filter(user=user, is_configured=True).order_by("-updated_at", "-id").first())
        if cfg:
            return cfg

        cfg = cfg_from_obj(Config.objects.filter(user=user).order_by("-updated_at", "-id").first())
        if cfg:
            return cfg

    # 2) إعدادات admin / superuser كإعداد عام للمنصة
    try:
        User = get_user_model()
        admin_users = User.objects.filter(is_superuser=True)
        cfg = cfg_from_obj(
            Config.objects.filter(user__in=admin_users, is_configured=True)
            .order_by("-updated_at", "-id")
            .first()
        )
        if cfg:
            return cfg
    except Exception:
        pass

    # 3) أي إعداد مكتمل ومفعّل
    cfg = cfg_from_obj(Config.objects.filter(is_configured=True).order_by("-updated_at", "-id").first())
    if cfg:
        return cfg

    # 4) آخر إعداد مكتمل حتى لو is_configured غير محدث
    for obj in Config.objects.order_by("-updated_at", "-id"):
        cfg = cfg_from_obj(obj)
        if cfg:
            return cfg

    return {}


@_inexc_quote_login_required
def quote_send_email(request, pk):
    import json
    import urllib.request
    import urllib.error
    from django.contrib import messages
    from django.shortcuts import redirect, get_object_or_404
    from django.utils.html import escape
    from .models import CRMQuote
    from .tenant_scope import crm_scope_queryset

    quote = get_object_or_404(crm_scope_queryset(request, CRMQuote), pk=pk)

    posted_email = ""
    if request.method == "POST":
        posted_email = (
            request.POST.get("customer_email")
            or request.POST.get("email")
            or request.POST.get("to_email")
            or ""
        ).strip()

    saved_email = (getattr(quote, "customer_email", "") or "").strip()
    contact_email = (getattr(getattr(quote, "contact", None), "email", "") or "").strip()
    company_email = (getattr(getattr(quote, "company", None), "email", "") or "").strip()
    email = posted_email or saved_email or contact_email or company_email

    if posted_email and hasattr(quote, "customer_email"):
        quote.customer_email = posted_email
        fields = ["customer_email"]
        if hasattr(quote, "updated_at"):
            fields.append("updated_at")
        quote.save(update_fields=fields)

    if not email:
        messages.error(request, "فشل الإرسال: أدخل بريد العميل أولاً ثم اضغط إرسال.")
        return redirect(f"/crm/quotes/{quote.pk}/#send-email-section")

    cfg = _inexc_get_emailjs_config(request)

    if not cfg.get("service_id") or not cfg.get("template_id") or not cfg.get("public_key"):
        messages.error(request, "فشل الإرسال: إعدادات EmailJS غير مكتملة. تأكد من Service ID و Template ID و Public Key.")
        return redirect(f"/crm/quotes/{quote.pk}/#send-email-section")

    quote_number = str(getattr(quote, "quote_number", "") or f"QUOTE-{quote.pk}")
    title = str(getattr(quote, "title", "") or "عرض سعر")
    total = str(getattr(quote, "total", "") or "")
    currency = str(getattr(quote, "currency", "") or "AED")
    status = str(getattr(quote, "status", "") or "")
    customer = str(
        getattr(quote, "customer_name", "")
        or getattr(getattr(quote, "contact", None), "name", "")
        or getattr(getattr(quote, "company", None), "name", "")
        or "-"
    )

    detail_url = request.build_absolute_uri(f"/crm/quotes/{quote.pk}/")
    print_url = request.build_absolute_uri(f"/crm/quotes/{quote.pk}/print/")
    pdf_url = request.build_absolute_uri(f"/crm/quotes/{quote.pk}/pdf/")
    # بناء جدول البنود الكامل
    _items_rows = ""
    try:
        for _i, _it in enumerate(quote.items.all(), 1):
            _desc = escape(str(getattr(_it, "description", "") or ""))
            _qty = escape(str(getattr(_it, "quantity", "") or ""))
            _price = escape(str(getattr(_it, "unit_price", "") or ""))
            _line = escape(str(getattr(_it, "line_total", "") or ""))
            _items_rows += (
                f'<tr>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:center">{_i}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7">{_desc}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:center">{_qty}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:left">{_price}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:left;font-weight:bold">{_line} {escape(currency)}</td>'
                f'</tr>'
            )
    except Exception:
        _items_rows = ""
    _subtotal = str(getattr(quote, "subtotal", "") or "")
    _tax_rate = str(getattr(quote, "tax_rate", "") or "")
    _tax_amount = str(getattr(quote, "tax_amount", "") or "")

    html_message = f"""
    <div dir="rtl" style="font-family:Arial,Tahoma,sans-serif;background:#f6f8fb;padding:24px">
      <div style="max-width:680px;margin:auto;background:#fff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden">
        <div style="background:#0b4ea2;color:#fff;padding:24px;text-align:center">
          <h1 style="margin:0;font-size:22px">عرض سعر</h1>
          <p style="margin:8px 0 0;opacity:.9">{escape(quote_number)}</p>
        </div>
        <div style="padding:24px;color:#1f2937;line-height:1.9">
          <p>مرحباً {escape(customer)},</p>
          <p>نتشرف بتقديم عرض السعر التالي لكم: <b>{escape(title)}</b></p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <tr style="background:#0b4ea2;color:#fff">
              <th style="padding:10px">#</th>
              <th style="padding:10px">البيان</th>
              <th style="padding:10px">الكمية</th>
              <th style="padding:10px;text-align:left">السعر</th>
              <th style="padding:10px;text-align:left">الإجمالي</th>
            </tr>
            {_items_rows}
          </table>
          <div style="text-align:left;margin-top:16px">
            <p style="margin:4px 0">الفرعي: <b>{escape(_subtotal)} {escape(currency)}</b></p>
            <p style="margin:4px 0">الضريبة ({escape(_tax_rate)}%): <b>{escape(_tax_amount)} {escape(currency)}</b></p>
            <p style="font-size:20px;font-weight:bold;color:#0b4ea2;margin-top:8px">الإجمالي: {escape(total)} {escape(currency)}</p>
          </div>
          <p style="text-align:center;margin-top:24px">
            <a href="{escape(print_url)}" style="background:#0b4ea2;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block">عرض / طباعة</a>
            &nbsp;
            <a href="{escape(pdf_url)}" style="background:#1565c0;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block">تحميل PDF</a>
          </p>
          <p style="color:#64748b;margin-top:16px">مع التحية.</p>
        </div>
      </div>
    </div>
    """

    plain_message = (
        f"عرض سعر {quote_number}\n"
        f"العنوان: {title}\n"
        f"العميل: {customer}\n"
        f"الإجمالي: {total} {currency}\n"
        f"رابط العرض: {print_url}\n"
        f"رابط PDF: {pdf_url}"
    )

    payload = {
        "service_id": cfg["service_id"],
        "template_id": cfg["template_id"],
        "user_id": cfg["public_key"],
        "template_params": {
            "to_email": email,
            "email": email,
            "customer_email": email,
            "recipient_email": email,
            "reply_to": cfg.get("sender_email") or "info@inexc.com",
            "from_name": cfg.get("sender_name") or "INEXC",
            "from_email": cfg.get("sender_email") or "info@inexc.com",
            "subject": f"عرض سعر {quote_number}",
            "quote_number": quote_number,
            "quote_title": title,
            "quote_total": total,
            "currency": currency,
            "customer_name": customer,
            "message": plain_message,
            "html_message": html_message,
            "detail_url": detail_url,
            "print_url": print_url,
            "pdf_url": pdf_url,
        },
    }

    if cfg.get("private_key"):
        payload["accessToken"] = cfg["private_key"]

    site_origin = request.build_absolute_uri("/").rstrip("/")

    req = urllib.request.Request(
        "https://api.emailjs.com/api/v1.0/email/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Origin": site_origin,
            "Referer": site_origin + "/",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", "ignore")
            code = resp.getcode()
        if 200 <= code < 300:
            messages.success(request, f"تم إرسال عرض السعر إلى {email} بنجاح عبر EmailJS.")
        else:
            messages.error(request, f"فشل EmailJS: HTTP {code} - {body[:300]}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        messages.error(request, f"فشل EmailJS: HTTP {exc.code} - {detail[:300]}")
    except Exception as exc:
        messages.error(request, f"فشل EmailJS: {exc}")

    return redirect(f"/crm/quotes/{quote.pk}/")



# INEXC_QUOTE_EMAIL_EXACT_WORKING_PAYLOAD
@_inexc_quote_login_required
def quote_send_email(request, pk):
    import json
    import urllib.request
    import urllib.error
    from django.contrib import messages
    from django.shortcuts import redirect, get_object_or_404
    from .models import CRMQuote
    from .tenant_scope import crm_scope_queryset

    quote = get_object_or_404(crm_scope_queryset(request, CRMQuote), pk=pk)

    posted_email = ""
    if request.method == "POST":
        posted_email = (
            request.POST.get("customer_email")
            or request.POST.get("email")
            or request.POST.get("to_email")
            or ""
        ).strip()

    saved_email = (getattr(quote, "customer_email", "") or "").strip()
    contact_email = (getattr(getattr(quote, "contact", None), "email", "") or "").strip()
    company_email = (getattr(getattr(quote, "company", None), "email", "") or "").strip()
    email = posted_email or saved_email or contact_email or company_email

    if posted_email and hasattr(quote, "customer_email"):
        quote.customer_email = posted_email
        fields = ["customer_email"]
        if hasattr(quote, "updated_at"):
            fields.append("updated_at")
        quote.save(update_fields=fields)

    if not email:
        messages.error(request, "فشل الإرسال: أدخل بريد العميل أولاً ثم اضغط إرسال.")
        return redirect(f"/crm/quotes/{quote.pk}/#send-email-section")

    from html import escape as _esc
    quote_number = str(getattr(quote, "quote_number", "") or f"QUOTE-{quote.pk}")
    title = str(getattr(quote, "title", "") or "عرض سعر")
    total = str(getattr(quote, "total", "") or "")
    currency = str(getattr(quote, "currency", "") or "AED")
    subtotal = str(getattr(quote, "subtotal", "") or "")
    tax_rate = str(getattr(quote, "tax_rate", "") or "")
    tax_amount = str(getattr(quote, "tax_amount", "") or "")
    customer = str(
        getattr(quote, "customer_name", "")
        or getattr(getattr(quote, "contact", None), "name", "")
        or getattr(getattr(quote, "company", None), "name", "")
        or "-"
    )
    print_url = request.build_absolute_uri(f"/crm/quotes/{quote.pk}/print/")
    pdf_url = request.build_absolute_uri(f"/crm/quotes/{quote.pk}/pdf/")

    # جدول البنود الكامل
    items_rows = ""
    try:
        for i, it in enumerate(quote.items.all(), 1):
            d = _esc(str(getattr(it, "description", "") or ""))
            q = _esc(str(getattr(it, "quantity", "") or ""))
            p = _esc(str(getattr(it, "unit_price", "") or ""))
            lt = _esc(str(getattr(it, "line_total", "") or ""))
            items_rows += (
                f'<tr><td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:center">{i}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7">{d}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:center">{q}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:left">{p}</td>'
                f'<td style="padding:10px;border-bottom:1px solid #eef2f7;text-align:left;font-weight:bold">{lt} {_esc(currency)}</td></tr>'
            )
    except Exception:
        items_rows = ""

    html_message = f"""
    <div dir="rtl" style="font-family:Arial,Tahoma,sans-serif;background:#f6f8fb;padding:24px">
      <div style="max-width:680px;margin:auto;background:#fff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden">
        <div style="background:#0b4ea2;color:#fff;padding:24px;text-align:center">
          <h1 style="margin:0;font-size:22px">عرض سعر</h1>
          <p style="margin:8px 0 0;opacity:.9">{_esc(quote_number)}</p>
        </div>
        <div style="padding:24px;color:#1f2937;line-height:1.9">
          <p>مرحباً {_esc(customer)},</p>
          <p>نتشرف بتقديم عرض السعر التالي: <b>{_esc(title)}</b></p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <tr style="background:#0b4ea2;color:#fff">
              <th style="padding:10px">#</th><th style="padding:10px">البيان</th>
              <th style="padding:10px">الكمية</th><th style="padding:10px;text-align:left">السعر</th>
              <th style="padding:10px;text-align:left">الإجمالي</th>
            </tr>
            {items_rows}
          </table>
          <div style="text-align:left;margin-top:16px">
            <p style="margin:4px 0">الفرعي: <b>{_esc(subtotal)} {_esc(currency)}</b></p>
            <p style="margin:4px 0">الضريبة ({_esc(tax_rate)}%): <b>{_esc(tax_amount)} {_esc(currency)}</b></p>
            <p style="font-size:20px;font-weight:bold;color:#0b4ea2;margin-top:8px">الإجمالي: {_esc(total)} {_esc(currency)}</p>
          </div>
          <p style="text-align:center;margin-top:24px">
            <a href="{_esc(print_url)}" style="background:#0b4ea2;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block">عرض / طباعة</a>
            &nbsp;
            <a href="{_esc(pdf_url)}" style="background:#1565c0;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block">تحميل PDF</a>
          </p>
          <p style="color:#64748b;margin-top:16px">مع التحية.</p>
        </div>
      </div>
    </div>
    """
    plain_message = (
        f"عرض سعر {quote_number}\n"
        f"العنوان: {title}\n"
        f"العميل: {customer}\n"
        f"الإجمالي: {total} {currency}\n"
        f"رابط العرض: {print_url}\n"
        f"رابط PDF: {pdf_url}"
    )

    # نفس طريقة التسجيل الناجحة: send_via_emailjs مع user
    try:
        from apps.campaigns.emailjs_service import send_via_emailjs
        result = send_via_emailjs(
            to_email=email,
            to_name=customer,
            subject=f"عرض سعر {quote_number}",
            body_html=html_message,
            body_text=plain_message,
            extra_params={
                "quote_number": quote_number,
                "quote_title": title,
                "quote_total": total,
                "currency": currency,
                "customer_name": customer,
                "print_url": print_url,
                "pdf_url": pdf_url,
            },
            user=request.user,
        )
        if result.get("success"):
            messages.success(request, f"تم إرسال عرض السعر إلى {email} بنجاح.")
        else:
            messages.error(request, f"تعذر إرسال البريد: {result.get('error', 'خطأ غير معروف')}")
    except Exception as exc:
        messages.error(request, f"فشل الإرسال: {exc}")

    return redirect(f"/crm/quotes/{quote.pk}/")