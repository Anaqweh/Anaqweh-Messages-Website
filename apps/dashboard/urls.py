from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("landing-demo-requests/", views.landing_demo_requests, name="landing_demo_requests"),
    path('landing-page/', views.landing_page_admin, name='landing_page_admin'),
    path("", views.dashboard_home, name="home"),
    path("search/", views.global_search, name="global_search"),
    path("dismiss-onboarding/", views.dismiss_onboarding, name="dismiss_onboarding"),
    path("companies/", views.companies, name="companies"),
    path("customers/", views.customers, name="customers"),
    path("registrations/", views.registrations, name="registrations"),
    path("payments/", views.payments, name="payments"),
    path("customers/add/", views.customer_add, name="customer_add"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),
    path("subscriptions/", views.subscriptions, name="subscriptions"),
    path("subscriptions/plan/add/", views.plan_add, name="plan_add"),
    path("subscriptions/save/", views.subscription_save, name="subscription_save"),
    path("subscriptions/<int:pk>/renew/", views.subscription_renew, name="subscription_renew"),
    path("subscriptions/<int:pk>/toggle/", views.subscription_toggle, name="subscription_toggle"),
]
