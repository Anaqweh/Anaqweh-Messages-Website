from django.urls import path

from . import views

app_name = "platform_core"

urlpatterns = [
    path("", views.home, name="home"),
    path("settings/", views.platform_settings, name="platform_settings"),
    path("finance/", views.platform_finance, name="platform_finance"),
    path("payouts/", views.platform_payouts, name="platform_payouts"),
    path("tenants/", views.tenant_list, name="tenant_list"),
    path("tenants/new/", views.tenant_create, name="tenant_create"),
    path("tenants/wizard/", views.tenant_wizard, name="tenant_wizard"),
    path("tenants/<int:pk>/", views.tenant_detail, name="tenant_detail"),
    path("tenants/<int:pk>/members/", views.tenant_members, name="tenant_members"),
    path("tenants/<int:pk>/edit/", views.tenant_edit, name="tenant_edit"),
    path("tenants/<int:pk>/delete/", views.tenant_delete, name="tenant_delete"),
    path("tenants/<int:pk>/managers/add/", views.tenant_add_manager, name="tenant_add_manager"),
    path("members/<int:membership_pk>/permissions/", views.tenant_member_permissions, name="tenant_member_permissions"),
    path("members/<int:membership_pk>/toggle/", views.tenant_member_toggle, name="tenant_member_toggle"),
    path("members/<int:membership_pk>/delete/", views.tenant_member_delete, name="tenant_member_delete"),
    path("switch-tenant/<int:tenant_id>/", views.switch_tenant_context, name="switch_tenant"),
    path("clear-tenant/", views.clear_tenant_context, name="clear_tenant"),
    path("tenants/<int:pk>/add-member/", views.tenant_add_member_page, name="tenant_add_member"),
    path("tenants/<int:pk>/roles/", views.tenant_roles, name="tenant_roles"),
    path("tenants/<int:pk>/roles/new/", views.tenant_role_create, name="tenant_role_create"),
    path("tenants/<int:pk>/roles/<int:role_pk>/edit/", views.tenant_role_edit, name="tenant_role_edit"),
    path("tenants/<int:pk>/roles/<int:role_pk>/delete/", views.tenant_role_delete, name="tenant_role_delete"),
    path("members/<int:membership_pk>/edit/", views.tenant_member_edit, name="tenant_member_edit"),
    path("members/<int:membership_pk>/reset-password/", views.tenant_member_reset_password, name="tenant_member_reset_password"),
    path("members/<int:membership_pk>/set-new-password/", views.tenant_member_set_password, name="tenant_member_set_password"),
]
