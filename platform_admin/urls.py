from django.urls import path

from . import views


app_name = "platform_admin"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("students/", views.students_list, name="students"),
    path("students/<int:pk>/", views.student_detail, name="student_detail"),
    path("students/<int:pk>/<slug:action>/", views.student_action, name="student_action"),
    path("teachers/", views.teachers_list, name="teachers"),
    path("teachers/<int:pk>/", views.teacher_detail, name="teacher_detail"),
    path("teachers/<int:pk>/<slug:action>/", views.teacher_action, name="teacher_action"),
    path("courses/", views.courses_list, name="courses"),
    path("courses/review/", views.courses_review, name="courses_review"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("courses/<int:pk>/<slug:action>/", views.course_action, name="course_action"),
    path("courses/<int:course_pk>/lessons/new/", views.lesson_editor, name="lesson_create"),
    path("courses/<int:course_pk>/lessons/<int:lesson_pk>/edit/", views.lesson_editor, name="lesson_edit"),
    path("payments/", views.payments_list, name="payments"),
    path("payments/<int:pk>/", views.payment_detail, name="payment_detail"),
    path("payments/<int:pk>/proof/", views.payment_proof, name="payment_proof"),
    path("payments/<int:pk>/<slug:action>/", views.payment_action, name="payment_action"),
    path("ai/", views.ai_overview, name="ai_overview"),
    path("ai/tutor-logs/", views.ai_tutor_logs, name="ai_tutor_logs"),
    path("ai/datasets/", views.ai_dataset_review, name="ai_datasets"),
    path("ai/datasets/<slug:action>/", views.ai_dataset_action, name="ai_dataset_action"),
    path("ai/model-metrics/", views.ai_model_metrics, name="ai_model_metrics"),
    path("analytics/", views.analytics_overview, name="analytics"),
    path("analytics/learning/", views.analytics_learning, name="analytics_learning"),
    path("analytics/payments/", views.analytics_payments, name="analytics_payments"),
    path("analytics/retention/", views.analytics_retention, name="analytics_retention"),
    path("settings/", views.settings_roles, name="settings_roles"),
    path("settings/notifications/", views.settings_notifications, name="settings_notifications"),
    path("settings/gamification/", views.settings_gamification, name="settings_gamification"),
    path("settings/platform/", views.settings_platform, name="settings_platform"),
    path("audit-logs/", views.audit_logs, name="audit_logs"),
]
