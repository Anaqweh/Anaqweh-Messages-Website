from django.urls import path
from . import views
from . import tenant_access_views

app_name = 'accounting'

urlpatterns = [
    path('customers/', views.customers, name='customers'),
    path('customers/new/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('reports/', views.reports, name='reports'),
    path('reports/export/csv/', views.reports_export_csv, name='reports_export_csv'),
    path('reports/export/xlsx/', views.reports_export_xlsx, name='reports_export_xlsx'),

    # رواتب الموظفين (HR + Payroll)
    path('employees/', tenant_access_views.employees, name='employees'),
    path('employees/new/', views.employee_create, name='employee_create'),
    path('employees/<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),
    path('payroll/', views.payrolls, name='payrolls'),
    path('payroll/create/', views.payroll_create, name='payroll_create'),
    path('payroll/<int:pk>/', views.payroll_detail, name='payroll_detail'),
    path('payroll/<int:pk>/approve/', views.payroll_approve, name='payroll_approve'),
    path('payroll/<int:pk>/delete/', views.payroll_delete, name='payroll_delete'),
]
