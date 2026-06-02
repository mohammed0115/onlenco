from django.urls import path

from . import views

app_name = "ai_usage_api"

urlpatterns = [
    path("summary/today/", views.summary_today, name="summary_today"),
    path("summary/month/", views.summary_month, name="summary_month"),
    path("daily/", views.daily, name="daily"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("features/", views.features, name="features"),
    path("models/", views.models, name="models"),
    path("limits/me/", views.limits_me, name="limits_me"),
    path("recalculate/", views.recalculate, name="recalculate"),
]
