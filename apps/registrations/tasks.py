from celery import shared_task


@shared_task
def send_daily_client_reminders():
    """تذكيرات متابعة العملاء الصباحية — لكل شركة على بريد مديرها، من بريد المنصة."""
    import datetime
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    from apps.platform_core.models import Tenant, TenantMembership
    from apps.registrations.models import RegClient
    from apps.campaigns.emailjs_service import send_via_emailjs

    U = get_user_model()
    sender = U.objects.filter(is_superuser=True).order_by("id").first()
    if not sender:
        return {"error": "no superuser"}

    today = timezone.localdate()
    tomorrow = today + datetime.timedelta(days=1)
    ST_COLORS = {
        "potential": ("#eef2ff", "#4f46e5"), "followup": ("#fff7e6", "#b45309"),
        "deposit": ("#e0f2fe", "#0369a1"), "registered": ("#e6f7ee", "#0f9d58"),
        "client": ("#dcfce7", "#15803d"), "not_interested": ("#f1f5f9", "#64748b"),
    }

    def row(c):
        bg, fg = ST_COLORS.get(c.status, ("#f1f5f9", "#64748b"))
        emp = f' &nbsp;\U0001F464 \u0627\u0644\u0645\u0633\u0624\u0648\u0644: {c.employee.name}' if c.employee else ""
        notes = ""
        if (c.notes or "").strip():
            n = c.notes.strip()[:60]
            notes = f'<div style="font-size:12px;color:#94a3b8;margin:3px 0 0">\U0001F4DD {n}...</div>'
        return (f'<div style="padding:10px 0;border-bottom:1px solid #f1f5f9">'
                f'<b style="color:#1e293b">{c.name}</b> \u2014 <span dir="ltr">{c.phone}</span>'
                f' &nbsp;<span style="background:{bg};color:{fg};border-radius:999px;padding:2px 10px;font-size:12px;font-weight:700">{c.get_status_display()}</span>'
                f'<span style="color:#475569;font-size:13px">{emp}</span>{notes}</div>')

    def build_html(mgr_name, due_today, due_tomorrow):
        sec_t = ""
        if due_today:
            sec_t = ('<h3 style="color:#b91c1c;font-size:15px;margin:18px 0 6px">\u2757 \u0645\u0633\u062a\u062d\u0642\u0629 \u0627\u0644\u064a\u0648\u0645 (%d)</h3>' % len(due_today)) + "".join(row(c) for c in due_today)
        sec_m = ""
        if due_tomorrow:
            sec_m = ('<h3 style="color:#b45309;font-size:15px;margin:18px 0 6px">\u23F0 \u063a\u062f\u0627\u064b (%d)</h3>' % len(due_tomorrow)) + "".join(row(c) for c in due_tomorrow)
        return (f'<div style="max-width:620px;margin:0 auto;background:#fff;direction:rtl;font-family:Tajawal,Arial,sans-serif;border:1px solid #e8eef5;border-radius:14px;overflow:hidden">'
                f'<div style="background:linear-gradient(135deg,#1e3a6e,#0b4ea2);color:#fff;padding:18px 22px;font-weight:800;font-size:17px">\U0001F514 \u062a\u0630\u0643\u064a\u0631\u0627\u062a \u0645\u062a\u0627\u0628\u0639\u0629 \u0627\u0644\u0639\u0645\u0644\u0627\u0621</div>'
                f'<div style="padding:20px 22px">'
                f'<p style="margin:0 0 4px;color:#334155">\u0645\u0631\u062d\u0628\u0627\u064b <b>{mgr_name}</b>\u060c</p>'
                f'<p style="margin:0;color:#64748b;font-size:14px">\u0644\u062f\u064a\u0643 \u0645\u0648\u0627\u0639\u064a\u062f \u0645\u062a\u0627\u0628\u0639\u0629 \u0645\u0633\u062a\u062d\u0642\u0629 \u0641\u064a \u0646\u0638\u0627\u0645 \u0625\u062f\u0627\u0631\u0629 \u0627\u0644\u0639\u0645\u0644\u0627\u0621:</p>'
                f'{sec_t}{sec_m}'
                f'<div style="text-align:center;margin:22px 0 6px"><a href="https://inexcsuite.com/registrations/clients/" style="background:#0b4ea2;color:#fff;padding:11px 30px;border-radius:10px;text-decoration:none;font-weight:800">\u0641\u062a\u062d \u0635\u0641\u062d\u0629 \u0627\u0644\u0639\u0645\u0644\u0627\u0621 \u2190</a></div>'
                f'<p style="color:#94a3b8;font-size:11px;margin:14px 0 0;text-align:center">\u062a\u0635\u0644\u0643 \u0647\u0630\u0647 \u0627\u0644\u0631\u0633\u0627\u0644\u0629 \u062a\u0644\u0642\u0627\u0626\u064a\u0627\u064b \u0643\u0644 \u0635\u0628\u0627\u062d \u0639\u0646\u062f \u0648\u062c\u0648\u062f \u0645\u0648\u0627\u0639\u064a\u062f \u0645\u062a\u0627\u0628\u0639\u0629. \u2014 \u0641\u0631\u064a\u0642 inexcsuite</p>'
                f'</div></div>')

    targets = []
    qs0 = RegClient.objects.filter(tenant__isnull=True, reminder_date__in=[today, tomorrow]).select_related("employee")
    if qs0.exists() and sender.email:
        targets.append((sender.email, sender.get_full_name() or sender.username, list(qs0)))
    for t in Tenant.objects.all():
        if not (t.modules or {}).get("registrations", False):
            continue
        qs = RegClient.objects.filter(tenant=t, reminder_date__in=[today, tomorrow]).select_related("employee")
        if not qs.exists():
            continue
        mb = (TenantMembership.objects.filter(tenant=t, is_tenant_admin=True).select_related("user").first()
              or TenantMembership.objects.filter(tenant=t).select_related("user").first())
        if mb and mb.user.email:
            targets.append((mb.user.email, mb.user.get_full_name() or mb.user.username, list(qs)))

    results = {"sent": 0, "failed": 0, "skipped_no_email": 0, "details": []}
    for email, name, clients in targets:
        due_t = [c for c in clients if c.reminder_date == today]
        due_m = [c for c in clients if c.reminder_date == tomorrow]
        subject = "\U0001F514 \u062a\u0630\u0643\u064a\u0631\u0627\u062a \u0645\u062a\u0627\u0628\u0639\u0629 \u0627\u0644\u0639\u0645\u0644\u0627\u0621 \u0627\u0644\u064a\u0648\u0645 \u2014 %d \u0639\u0645\u064a\u0644" % len(clients)
        try:
            r = send_via_emailjs(to_email=email, to_name=name, subject=subject,
                                 body_html=build_html(name, due_t, due_m), user=sender)
            if r.get("success"):
                results["sent"] += 1
            else:
                results["failed"] += 1
            results["details"].append({"to": email, "n": len(clients), "ok": r.get("success"), "err": r.get("error", "")[:80]})
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"to": email, "err": str(e)[:80]})
    return results
