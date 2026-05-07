from django.urls import path
from . import views

urlpatterns = [
    path("", views.placement, name="placement"),
    path("retake/", views.start_retake, name="placement_retake"),
]
