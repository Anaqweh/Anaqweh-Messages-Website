from django.urls import path

from . import workspace_views

app_name = "workspace"

urlpatterns = [
    path("access-denied/", workspace_views.access_denied, name="access_denied"),
    path("finance/", workspace_views.finance, name="finance"),
    path("", workspace_views.home, name="home"),
    path("registration-settings/", workspace_views.workspace_registration_settings, name="registration_settings"),
    path("members/", workspace_views.workspace_members, name="members"),
    path("members/add/", workspace_views.workspace_member_add, name="member_add"),
    path("members/<int:membership_pk>/edit/", workspace_views.workspace_member_edit, name="member_edit"),
    path("roles/", workspace_views.workspace_roles, name="roles"),
    path("stripe-settings/", workspace_views.workspace_stripe_settings, name="stripe_settings"),
    path("finance-board/", workspace_views.workspace_finance_board, name="finance_board"),
    path("payout-request/", workspace_views.workspace_payout_request, name="payout_request"),
    path("members/<int:membership_pk>/reset-password/", workspace_views.workspace_member_reset_password, name="member_reset_password"),
]
