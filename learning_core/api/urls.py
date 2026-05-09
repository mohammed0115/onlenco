from django.urls import path

from . import views

app_name = "learning_api"

urlpatterns = [
    path("learning/profile/", views.LearningProfileView.as_view(), name="profile"),
    path("learning/mastery/", views.SkillMasteryListView.as_view(), name="mastery"),
    path("learning/weaknesses/", views.WeaknessListView.as_view(), name="weaknesses"),
    path("learning/errors/", views.UserErrorListView.as_view(), name="errors"),
    path(
        "learning/recommendations/",
        views.RecommendationListView.as_view(),
        name="recommendations",
    ),
    path("exercises/generate/", views.GenerateExercisesView.as_view(), name="exercises_generate"),
    path("exercises/next/", views.NextExerciseView.as_view(), name="exercises_next"),
    path("exercises/micro/", views.MicroPracticeView.as_view(), name="exercises_micro"),
    path(
        "exercises/<int:exercise_id>/attempt/",
        views.ExerciseAttemptView.as_view(),
        name="exercises_attempt",
    ),
    path("analyze-text/", views.AnalyzeTextView.as_view(), name="analyze_text"),
    path("tutor/chat/", views.TutorChatApiView.as_view(), name="tutor_chat"),
    path("tutor/voice/", views.TutorVoiceApiView.as_view(), name="tutor_voice"),
    path("placement/submit/", views.PlacementSubmitApiView.as_view(), name="placement_submit"),
    path(
        "placement/speaking/",
        views.PlacementSpeakingUploadApiView.as_view(),
        name="placement_speaking",
    ),
    path("health/", views.health_check, name="health"),
]
