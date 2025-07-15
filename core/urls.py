from django.urls import path
from .views import LandingPageView, autoservice_detail_view
from django.conf import settings
from django.conf.urls.static import static

app_name = "core"

urlpatterns = [
    path(
        "<slug:autoservice_slug>/", autoservice_detail_view, name="autoservice_detail"
    ),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
