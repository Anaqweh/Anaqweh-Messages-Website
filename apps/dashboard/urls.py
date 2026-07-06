from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="home"),
    path("companies/", views.companies, name="companies"),
    path("customers/", views.customers, name="customers"),
    path("registrations/", views.registrations, name="registrations"),
    path("payments/", views.payments, name="payments"),
    path("customers/add/", views.customer_add, name="customer_add"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),
]
