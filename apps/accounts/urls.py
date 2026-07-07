from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',              views.login_view,       name='login'),
    path('logout/',             views.logout_view,      name='logout'),
    path('verify-2fa/', views.verify_2fa_view, name='verify_2fa'),
    path('setup-2fa/', views.setup_2fa_view, name='setup_2fa'),
    path('profile/',            views.profile_view,     name='profile'),
    path('users/',              views.user_list,        name='user_list'),
    path('users/new/',          views.user_create,      name='user_create'),
    path('users/<int:pk>/delete/', views.user_delete,   name='user_delete'),
    path('audit-log/',          views.audit_log_view,   name='audit_log'),
    path('users/<int:pk>/edit/',           views.user_edit,           name='user_edit'),
    path('users/<int:pk>/toggle/',         views.user_toggle,         name='user_toggle'),
    path('users/<int:pk>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('users/<int:pk>/detail/',         views.user_detail,         name='user_detail'),
    path('emailjs-settings/',   views.emailjs_settings, name='emailjs_settings'),
    path('emailjs-test/',       views.emailjs_test,     name='emailjs_test'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-code/', views.verify_reset_code, name='verify_reset_code'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('forgot-username/', views.forgot_username, name='forgot_username'),
]
