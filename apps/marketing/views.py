from django.http import HttpResponse
from django.shortcuts import render, redirect


def landing_page(request):
    return landing(request)


def robots_txt(request):
    body = """User-agent: *
Allow: /landing/
Disallow: /dashboard/
Disallow: /payments/
Disallow: /accounting/
Disallow: /crm/
Disallow: /registrations/
Disallow: /accounts/
Disallow: /django-admin/
Sitemap: https://inexcsuite.com/sitemap.xml
"""
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    body = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://inexcsuite.com/landing/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
"""
    return HttpResponse(body, content_type="application/xml; charset=utf-8")


def landing(request):
    from django.shortcuts import render
    plans = []
    try:
        from apps.platform_core.models import SubscriptionPlan
        plans = list(SubscriptionPlan.objects.filter(is_active=True, show_on_landing=True).order_by("sort_order", "price_monthly"))
        for p in plans:
            p.feature_list = [ln.strip() for ln in (p.features or "").splitlines() if ln.strip()]
    except Exception:
        plans = []
    lc = None
    try:
        from apps.platform_core.models import LandingContent
        lc = LandingContent.get_solo()
    except Exception:
        lc = None
    clients = []
    try:
        from apps.platform_core.models import LandingClient
        clients = list(LandingClient.objects.filter(is_active=True).order_by("sort_order", "name"))
    except Exception:
        clients = []
    return render(request, "marketing/landing.html", {"plans": plans, "lc": lc, "clients": clients})


def _landing_demo_ip(request):
    raw = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or ""
    value = raw.split(",", 1)[0].strip()
    return value or None


def _landing_demo_whatsapp_url(data):
    from urllib.parse import quote

    target_phone = "".join(["971", "543", "475", "500"])
    msg = "\n".join([
        "طلب عرض تجريبي لـ inexcsuite",
        "الاسم: " + (data.get("name") or "-"),
        "الجهة: " + (data.get("company") or "-"),
        "رقم التواصل: " + (data.get("phone") or "-"),
        "البريد: " + (data.get("email") or "-"),
        "الاهتمام: " + (data.get("focus") or "-"),
        "ملاحظة: " + (data.get("message") or "-"),
    ])
    return "https://wa.me/" + target_phone + "?text=" + quote(msg)


def demo_request(request):
    from datetime import timedelta
    from django.http import JsonResponse
    from django.utils import timezone
    from apps.platform_core.models import LandingDemoRequest

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST only"}, status=405)

    data = {
        "name": (request.POST.get("name") or "").strip(),
        "company": (request.POST.get("company") or "").strip(),
        "phone": (request.POST.get("phone") or "").strip(),
        "email": (request.POST.get("email") or "").strip(),
        "focus": (request.POST.get("focus") or "").strip(),
        "message": (request.POST.get("message") or "").strip(),
    }

    if request.POST.get("website"):
        return JsonResponse({"success": True, "whatsapp_url": _landing_demo_whatsapp_url(data)})

    if not data["name"] or not data["phone"]:
        return JsonResponse({"success": False, "error": "name and phone are required"}, status=400)

    ip = _landing_demo_ip(request)
    if ip:
        since = timezone.now() - timedelta(hours=1)
        if LandingDemoRequest.objects.filter(ip_address=ip, created_at__gte=since).count() >= 20:
            return JsonResponse({"success": False, "error": "too many requests"}, status=429)

    lead = LandingDemoRequest.objects.create(
        name=data["name"],
        company=data["company"],
        phone=data["phone"],
        email=data["email"],
        focus=data["focus"],
        message=data["message"],
        ip_address=ip,
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:1000],
    )

    whatsapp_url = _landing_demo_whatsapp_url(data)

    wants_json = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("accept") or "")
        or request.POST.get("_json") == "1"
    )

    if wants_json:
        return JsonResponse({
            "success": True,
            "id": lead.pk,
            "whatsapp_url": whatsapp_url,
        })

    from django.http import HttpResponse
    from html import escape as _escape
    import json as _json

    safe_url = _escape(whatsapp_url, quote=True)
    script_url = _json.dumps(whatsapp_url)

    return HttpResponse(f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تم إرسال الطلب</title>
<meta http-equiv="refresh" content="1.6;url={safe_url}">
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f4f8ff;font-family:Tajawal,Arial,sans-serif;color:#10244a}}
.card{{width:min(520px,calc(100% - 32px));background:#fff;border:1px solid #dbe7f5;border-radius:24px;padding:34px;text-align:center;box-shadow:0 22px 55px rgba(22,52,98,.13)}}
.icon{{width:58px;height:58px;border-radius:18px;background:#ecfdf5;color:#047857;display:grid;place-items:center;margin:0 auto 18px;font-size:30px;font-weight:900}}
h1{{margin:0 0 10px;font-size:28px;color:#12366d}}
p{{margin:0;color:#60718f;line-height:1.9;font-size:18px}}
</style>
</head>
<body>
<div class="card">
  <div class="icon">✓</div>
  <h1>تم إرسال الطلب بنجاح</h1>
  <p>سيتم التواصل معك من قبل الفريق، وسيتم فتح واتساب الآن.</p>
</div>
<script>
setTimeout(function(){{ window.location.href = {script_url}; }}, 1600);
</script>
</body>
</html>""")

def _legal_lc():
    try:
        from apps.platform_core.models import LandingContent
        return LandingContent.get_solo()
    except Exception:
        return None


def privacy(request):
    from django.shortcuts import render
    return render(request, "marketing/legal.html", {"page": "privacy", "lc": _legal_lc()})


def terms(request):
    from django.shortcuts import render
    return render(request, "marketing/legal.html", {"page": "terms", "lc": _legal_lc()})
