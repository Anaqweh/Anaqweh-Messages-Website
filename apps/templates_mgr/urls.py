from django.urls import path
from . import views
app_name = 'templates_mgr'
urlpatterns = [
    path('', views.template_list, name='template_list'),
    path('new/', views.template_create, name='template_create'),
    path('<int:pk>/', views.template_detail, name='template_detail'),
    path('<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('<int:pk>/delete/', views.template_delete, name='template_delete'),
]
