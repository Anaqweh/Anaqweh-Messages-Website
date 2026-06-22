from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    path('', views.task_dashboard, name='dashboard'),
    path('list/', views.task_list, name='task_list'),
    path('new/', views.task_create, name='task_create'),
    path('<int:pk>/', views.task_detail, name='task_detail'),
    path('<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('<int:pk>/move/', views.task_move_stage, name='task_move'),
    path('<int:pk>/comment/', views.task_add_comment, name='task_comment'),
    path('<int:pk>/attach/', views.task_add_attachment, name='task_attach'),
    path('kanban/', views.task_kanban, name='kanban'),
    path('workflows/', views.workflow_list, name='workflow_list'),
    path('workflows/new/', views.workflow_create, name='workflow_create'),
    path('workflows/<int:pk>/edit/', views.workflow_edit, name='workflow_edit'),
]
