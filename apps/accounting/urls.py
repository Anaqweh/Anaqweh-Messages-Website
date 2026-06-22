from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('customers/', views.customers, name='customers'),
    path('customers/new/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('reports/', views.reports, name='reports'),
    path('reports/export/csv/', views.reports_export_csv, name='reports_export_csv'),
    path('reports/export/xlsx/', views.reports_export_xlsx, name='reports_export_xlsx'),
]
