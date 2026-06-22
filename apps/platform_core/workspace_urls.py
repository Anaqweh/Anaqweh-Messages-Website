from django.urls import path

from . import workspace_views

app_name = "workspace"

urlpatterns = [
    path("access-denied/", workspace_views.access_denied, name="access_denied"),
    path("finance/", workspace_views.finance, name="finance"),
    path("", workspace_views.home, name="home"),
    path("members/", workspace_views.workspace_members, name="members"),
    path("members/add/", workspace_views.workspace_member_add, name="member_add"),
    path("members/<int:membership_pk>/edit/", workspace_views.workspace_member_edit, name="member_edit"),
    path("roles/", workspace_views.workspace_roles, name="roles"),
    path("members/<int:membership_pk>/reset-password/", workspace_views.workspace_member_reset_password, name="member_reset_password"),
]
