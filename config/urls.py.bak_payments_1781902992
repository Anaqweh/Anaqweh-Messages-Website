from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('', include('apps.campaigns.urls', namespace='campaigns')),
    path('recipients/', include('apps.recipients.urls', namespace='recipients')),
    path('templates/', include('apps.templates_mgr.urls', namespace='templates_mgr')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
