from django.urls import path

from . import views


app_name = "courses"

urlpatterns = [
    path("<int:pk>/", views.course_detail, name="course_detail"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/",
         views.course_lesson_detail, name="lesson_detail"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/complete/",
         views.mark_lesson_complete, name="mark_lesson_complete"),
    path("<int:course_pk>/lessons/<int:lesson_pk>/quiz/",
         views.lesson_quiz_attempt, name="lesson_quiz_attempt"),
]
