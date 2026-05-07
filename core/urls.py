from django.http import JsonResponse
from django.urls import path
from . import views


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", healthz, name="healthz"),
]

handler404 = "core.views.not_found"
