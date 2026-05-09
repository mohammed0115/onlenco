from django.urls import path

from . import views

app_name = "motivation_api"

urlpatterns = [
    path("xp/", views.MotivationXPView.as_view(), name="xp"),
    path("achievements/", views.MotivationAchievementsView.as_view(), name="achievements"),
    path("badges/", views.MotivationBadgesView.as_view(), name="badges"),
    path("messages/", views.MotivationMessagesView.as_view(), name="messages"),
    path("challenges/", views.ChallengesView.as_view(), name="challenges"),
    path("leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
    path("run/", views.MotivationRunView.as_view(), name="run"),
]
