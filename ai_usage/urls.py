from django.urls import path

from . import views

app_name = "ai_usage"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("daily/", views.daily_report, name="daily_report"),
    path("students/", views.student_usage, name="student_usage"),
    path("export.csv", views.export_csv, name="export_csv"),
]
