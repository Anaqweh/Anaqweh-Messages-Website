from django.views.generic import RedirectView
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/img/favicon.png", permanent=True)),
    path('', include('apps.marketing.urls', namespace='marketing')),
    path('i18n/', include('django.conf.urls.i18n')),  # تبديل اللغة
    path('crm/', include('apps.crm.urls', namespace='crm')),
    path('tasks/', include('apps.tasks.urls', namespace='tasks')),
    path('workspace/', include('apps.platform_core.workspace_urls', namespace='workspace')),
    path('platform/', include('apps.platform_core.urls', namespace='platform_core')),
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
