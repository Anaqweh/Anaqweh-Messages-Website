from django.urls import path
from . import views
from . import tracking
app_name = 'campaigns'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('campaigns/', views.campaign_list, name='campaign_list'),
    path('campaigns/new/', views.campaign_create, name='campaign_create'),
    path('campaigns/test-send/', views.send_test_email, name='send_test'),
    path('campaigns/<int:pk>/', views.campaign_detail, name='campaign_detail'),
    path('campaigns/<int:pk>/stats/', views.campaign_stats_api, name='campaign_stats'),
    path('campaigns/<int:pk>/<str:action>/', views.campaign_action, name='campaign_action'),
    path('track/open/<int:log_id>/', tracking.track_open, name='track_open'),
    path('track/click/<int:log_id>/', tracking.track_click, name='track_click'),
    path('smart-send/', views.smart_send, name='smart_send'),
    path("smart-send/parse-excel/", views.parse_excel, name="parse_excel"),
    path('smart-send/do-send/', views.do_smart_send, name='do_smart_send'),
    path('smart-send/lists/', views.smart_send_lists, name='smart_send_lists'),
    path('smart-send/list-recipients/', views.smart_send_list_recipients, name='smart_send_list_recipients'),
]
