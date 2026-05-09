from django.urls import path

from . import views

app_name = "exams_api"

urlpatterns = [
    path("blueprints/", views.ExamBlueprintListView.as_view(), name="blueprints"),
    path("assemble/", views.AssembleExamView.as_view(), name="assemble"),
    path("<int:pk>/", views.ExamDetailView.as_view(), name="detail"),
    path("<int:pk>/start/", views.StartExamAttemptView.as_view(), name="start"),
    path("attempts/<int:pk>/submit/", views.SubmitExamAttemptView.as_view(), name="submit"),
    path("attempts/", views.MyAttemptsView.as_view(), name="attempts"),
    path("question-bank/stats/", views.QuestionBankStatsView.as_view(), name="bank_stats"),
]
