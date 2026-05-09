from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("lessons/<int:pk>/", views.lesson_detail, name="lesson_detail"),
    path("lessons/<int:pk>/video-done/", views.mark_video_complete, name="lesson_video_done"),
    path("lessons/<int:pk>/quiz/", views.quiz_attempt, name="lesson_quiz"),

    # Duolingo-style exam player + entry points.
    # Note: the result URL name is `lesson_exam_result` (not `exam_result`)
    # because the `exams` app already owns `name="exam_result"` for its
    # `ExamAttempt` results page. Two URLs sharing the same name made
    # `reverse()` non-deterministic; renaming this one avoids the clash.
    path("exam/daily/", views.daily_exam, name="exam_daily"),
    path("exam/<int:assessment_id>/", views.exam_play, name="exam_play"),
    path("exam/<int:assessment_id>/result/", views.exam_result, name="lesson_exam_result"),

    # Legacy alias — redirects to the new player
    path(
        "weekly/<int:assessment_id>/",
        views.weekly_assessment,
        name="weekly_assessment",
    ),
]
