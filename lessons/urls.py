from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("lessons/<int:pk>/", views.lesson_detail, name="lesson_detail"),
    path("lessons/<int:pk>/video-done/", views.mark_video_complete, name="lesson_video_done"),
    path("lessons/<int:pk>/quiz/", views.quiz_attempt, name="lesson_quiz"),
    path(
        "weekly/<int:assessment_id>/",
        views.weekly_assessment,
        name="weekly_assessment",
    ),
]
