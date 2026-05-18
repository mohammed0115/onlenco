from django.urls import path
from django.views.generic import RedirectView

from . import views


app_name = "courses"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="library", permanent=False), name="course_index"),
    path("<int:pk>/", views.course_detail, name="course_detail"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/",
         views.course_lesson_detail, name="lesson_detail"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/complete/",
         views.mark_lesson_complete, name="mark_lesson_complete"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/quiz/",
         views.lesson_quiz_attempt, name="lesson_quiz_attempt"),
]
