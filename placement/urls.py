from django.urls import path
from . import views

urlpatterns = [
    path("", views.placement, name="placement"),
    path("retake/", views.start_retake, name="placement_retake"),

    # Dynamic-bank flow (creates an attempt, picks 5+5 questions,
    # walks the student through written → speaking → result).
    path("start/",                     views.placement_start,    name="placement_start"),
    path("<int:attempt_id>/written/",  views.placement_written,  name="placement_written"),
    path("<int:attempt_id>/speaking/", views.placement_speaking, name="placement_speaking"),
    path("<int:attempt_id>/result/",   views.placement_result,   name="placement_result"),
]
