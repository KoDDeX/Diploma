from django.contrib import admin
from django.urls import path, include
from core.views import LandingPageView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", LandingPageView.as_view(), name="landing"),
    path("autoservice/", include("core.urls")),
    path("users/", include("users.urls")),
]
