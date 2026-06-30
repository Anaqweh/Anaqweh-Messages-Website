from django.urls import path
from . import views
from . import tenant_access_views

app_name = "registrations"

urlpatterns = [
    path('templates/<int:pk>/spark-fill/', tenant_access_views.spark_fill_form, name='spark_fill_form'),
    path("", views.dashboard, name="dashboard"),
    path("ocr/", views.ocr_id_image_disabled, name="ocr_id_image"),
    path("templates/new/", views.template_create, name="template_create"),
    path("templates/<int:pk>/edit/", views.template_edit, name="template_edit"),
    path("templates/<int:pk>/fill/", views.fill_form, name="fill_form"),
    path("templates/<int:pk>/spark-fill/", views.spark_fill_form, name="spark_fill_form"),
    path("submissions/<int:pk>/", views.submission_detail, name="submission_detail"),
    path("submissions/<int:pk>/edit/", views.submission_edit, name="submission_edit"),
    path("submissions/<int:pk>/delete/", views.submission_delete, name="submission_delete"),
    path("submissions/<int:pk>/email/", views.submission_email, name="submission_email"),
    path("submissions/<int:pk>/pdf/", views.submission_pdf, name="submission_pdf"),
    path("submissions/<int:pk>/spark-pdf/", views.spark_submission_pdf, name="spark_submission_pdf"),
]
