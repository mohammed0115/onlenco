from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
]

handler404 = "core.views.not_found"
