from django.urls import path

from . import views

app_name = "teacher_portal"

urlpatterns = [
    path("switch/<str:role>/", views.switch_role, name="switch_role"),
    path("switch-mode/<str:mode>/", views.switch_staff_mode, name="switch_staff_mode"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("courses/", views.courses_list, name="courses"),
    path("courses/create/", views.course_create, name="course_create"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("courses/<int:pk>/edit/", views.course_edit, name="course_edit"),
    path("courses/<int:pk>/delete/", views.course_delete, name="course_delete"),
    path("courses/<int:pk>/submit-review/", views.course_submit_review, name="course_submit_review"),
    path("courses/<int:course_id>/lessons/", views.lessons_list, name="lessons"),
    path("courses/<int:course_id>/lessons/create/", views.lesson_create, name="lesson_create"),
    path("lessons/", views.all_lessons, name="all_lessons"),
    path("lessons/<int:lesson_id>/edit/", views.lesson_edit, name="lesson_edit"),
    path("lessons/<int:lesson_id>/delete/", views.lesson_delete, name="lesson_delete"),
    path("lessons/<int:lesson_id>/submit-review/", views.lesson_submit_review, name="lesson_submit_review"),
    path("lessons/<int:lesson_id>/quiz/", views.lesson_quiz, name="lesson_quiz"),
    path("quizzes/", views.all_quizzes, name="all_quizzes"),
    path("quizzes/<int:quiz_id>/delete/", views.quiz_delete, name="quiz_delete"),
    path("quizzes/<int:quiz_id>/questions/", views.quiz_questions, name="quiz_questions"),
    path("questions/<int:question_id>/edit/", views.question_edit, name="question_edit"),
    path("questions/<int:question_id>/delete/", views.question_delete, name="question_delete"),
    path("students/", views.students_list, name="students"),
    path("students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("students/<int:student_id>/notes/", views.student_note_create, name="student_note_create"),
    path("notes/<int:note_id>/delete/", views.student_note_delete, name="student_note_delete"),
    path("assignments/", views.assignments_list, name="assignments"),
    path("assignments/create/", views.assignment_create, name="assignment_create"),
    path("assignments/<int:assignment_id>/", views.assignment_detail, name="assignment_detail"),
    path("assignments/<int:assignment_id>/delete/", views.assignment_delete, name="assignment_delete"),
    path("assignments/<int:assignment_id>/submit/", views.assignment_submit, name="assignment_submit"),
    path("submissions/<int:submission_id>/review/", views.submission_review, name="submission_review"),
    path("analytics/", views.analytics, name="analytics"),
    path("notifications/", views.notifications, name="notifications"),
    path("settings/", views.settings, name="settings"),
]
