"""Root URL configuration."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok", "service": "chainsentinel-api"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.api.urls")),
    path("healthz/", health, name="healthz"),
]

admin.site.site_header = "ChainSentinel Operations"
admin.site.site_title = "ChainSentinel Admin"
admin.site.index_title = "Platform administration"
