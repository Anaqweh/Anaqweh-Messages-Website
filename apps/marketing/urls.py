from . import views
from django.urls import path

from .views import landing_page, robots_txt, sitemap_xml

app_name = "marketing"

urlpatterns = [
    path("landing/demo-request/", views.demo_request, name="landing_demo_request"),
    path("", views.landing, name="landing"),
    path("demo-request/", views.demo_request, name="demo_request"),
    path("landing/", landing_page, name="landing"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
]
