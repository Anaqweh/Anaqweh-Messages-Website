from .models import AdminNotification


def admin_notifications(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"unread_notif_count": 0, "recent_notifications": [], "show_onboarding": False}
    if not user.is_superuser:
        show_onboarding = False
        try:
            from apps.platform_core.navigation import active_membership_for
            m = active_membership_for(user)
            if m and not m.onboarding_seen:
                show_onboarding = True
        except Exception:
            pass
        return {"unread_notif_count": 0, "recent_notifications": [], "show_onboarding": show_onboarding}
    try:
        from apps.platform_core.models import TenantSubscription
        from django.utils import timezone
        import datetime
        soon = timezone.now().date() + datetime.timedelta(days=7)
        expiring = TenantSubscription.objects.filter(
            status="active", end_date__lte=soon
        ).select_related("tenant")
        for sub in expiring:
            title = "اشتراك منتهٍ" if sub.is_expired else "اشتراك يوشك على الانتهاء"
            exists = AdminNotification.objects.filter(
                title=title, body__startswith=sub.tenant.name, is_read=False
            ).exists()
            if not exists:
                AdminNotification.objects.create(
                    title=title,
                    body=f"{sub.tenant.name} — ينتهي {sub.end_date}",
                    icon="bi-exclamation-circle" if sub.is_expired else "bi-clock-history",
                    url="/dashboard/subscriptions/",
                )
    except Exception:
        pass
    qs = AdminNotification.objects.all()[:8]
    show_onboarding = False
    try:
        from apps.platform_core.navigation import active_membership_for
        m = active_membership_for(user)
        if m and not m.onboarding_seen and not user.is_superuser:
            show_onboarding = True
    except Exception:
        pass
    return {
        "show_onboarding": show_onboarding,
        "unread_notif_count": AdminNotification.objects.filter(is_read=False).count(),
        "recent_notifications": qs,
    }
