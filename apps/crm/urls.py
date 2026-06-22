from django.urls import path
from . import views

app_name = "crm"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("companies/", views.company_list, name="company_list"),
    path("companies/new/", views.company_create, name="company_create"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("companies/<int:pk>/edit/", views.company_edit, name="company_edit"),
    path("companies/<int:pk>/delete/", views.company_delete, name="company_delete"),
    path("contacts/", views.contact_list, name="contact_list"),
    path("contacts/new/", views.contact_create, name="contact_create"),
    path("contacts/<int:pk>/", views.contact_detail, name="contact_detail"),
    path("contacts/<int:pk>/edit/", views.contact_edit, name="contact_edit"),
    path("contacts/<int:pk>/delete/", views.contact_delete, name="contact_delete"),
    path("deals/", views.deal_list, name="deal_list"),
    path("deals/new/", views.deal_create, name="deal_create"),
    path("deals/<int:pk>/", views.deal_detail, name="deal_detail"),
    path("deals/<int:pk>/edit/", views.deal_edit, name="deal_edit"),
    path("deals/<int:pk>/delete/", views.deal_delete, name="deal_delete"),
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/done/", views.task_done, name="task_done"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("quotes/", views.quote_list, name="quote_list"),
    path("quotes/new/", views.quote_create, name="quote_create"),
    path("quotes/<int:pk>/", views.quote_detail, name="quote_detail"),
    path("quotes/<int:pk>/edit/", views.quote_edit, name="quote_edit"),
    path("quotes/<int:pk>/delete/", views.quote_delete, name="quote_delete"),
    path("quotes/<int:pk>/pdf/", views.quote_pdf, name="quote_pdf"),
    path("quotes/<int:pk>/to-invoice/", views.quote_to_invoice, name="quote_to_invoice"),
    path("quotes/<int:pk>/send-email/", views.quote_send_email, name="quote_send_email"),
]

