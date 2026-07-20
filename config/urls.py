from django.views.generic import RedirectView
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve

from apps.marketing.views import seo_sitemap, seo_robots
from apps.dashboard.views import healthz

urlpatterns = [
    path("google082e6b72ef146463.html", lambda r: __import__("django.http", fromlist=["HttpResponse"]).HttpResponse("google-site-verification: google082e6b72ef146463.html", content_type="text/html")),
    path("sitemap.xml", seo_sitemap),
    path("robots.txt", seo_robots),
    path("healthz", healthz),
    path("maintenance-preview/", lambda r: __import__("django.shortcuts", fromlist=["render"]).render(r, "maintenance.html")),
    path("favicon.ico", RedirectView.as_view(url="/static/img/favicon.png", permanent=True)),
    path('', include('apps.marketing.urls', namespace='marketing')),
    path('i18n/', include('django.conf.urls.i18n')),  # تبديل اللغة
    path('crm/', include('apps.crm.urls', namespace='crm')),
    path('tasks/', include('apps.tasks.urls', namespace='tasks')),
    path('workspace/', include('apps.platform_core.workspace_urls', namespace='workspace')),
    path('platform/', include('apps.platform_core.urls', namespace='platform_core')),
    path('subscription-expired/', __import__('apps.platform_core.views', fromlist=['subscription_expired']).subscription_expired, name='subscription_expired'),
    path('payments/', include('apps.payments.urls', namespace='payments')),
    path('accounting/', include('apps.accounting.urls', namespace='accounting')),
    path('django-admin/', admin.site.urls),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('', include('apps.campaigns.urls', namespace='campaigns')),
    path('recipients/', include('apps.recipients.urls', namespace='recipients')),
    path('templates/', include('apps.templates_mgr.urls', namespace='templates_mgr')),
    path('registrations/', include('apps.registrations.urls', namespace='registrations')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
]

# خدمة الصور المرفوعة (media) دائماً عبر serve - تعمل حتى مع DEBUG=False
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = "inexcsuite — لوحة الإدارة"
admin.site.site_title = "inexcsuite"
admin.site.index_title = "إدارة النظام"
