from django.urls import path
from . import views
app_name = 'reports'
urlpatterns = [
    path('', views.reports_dashboard, name='dashboard'),
    path('campaign/<int:pk>/', views.campaign_report, name='campaign_report'),
    path('campaign/<int:pk>/export/csv/', views.export_campaign_csv, name='export_csv'),
    path('campaign/<int:pk>/export/xlsx/', views.export_campaign_excel, name='export_xlsx'),
    path('analytics/data/', views.analytics_api, name='analytics_api'),
    path('heatmap/data/', views.heatmap_api, name='heatmap_api'),
]
