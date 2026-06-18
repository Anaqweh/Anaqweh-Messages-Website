from django.urls import path
from . import views
app_name = 'recipients'
urlpatterns = [
    path('', views.list_view, name='list_view'),
    path('new/', views.list_create, name='list_create'),
    path('<int:pk>/', views.list_detail, name='list_detail'),
    path('<int:list_pk>/add/', views.recipient_add, name='recipient_add'),
    path('<int:list_pk>/upload/', views.upload_file, name='upload_file'),
    path('<int:list_pk>/upload/<int:batch_pk>/column/', views.upload_choose_column, name='upload_choose_column'),
    path('recipient/<int:pk>/edit/', views.recipient_edit, name='recipient_edit'),
    path('recipient/<int:pk>/delete/', views.recipient_delete, name='recipient_delete'),
    path('unsubscribe/', views.unsubscribe_list_view, name='unsubscribe_list'),
    path('unsubscribe/<str:email>/', views.unsubscribe_public, name='unsubscribe'),
    path('<int:pk>/clean/', views.clean_list, name='clean_list'),
    path('<int:pk>/segment/', views.segment_list, name='segment_list'),
]
