from django.urls import path

from .views import NotificationPreferencesView

app_name = "notifications_api"

urlpatterns = [
    path(
        "preferences/",
        NotificationPreferencesView.as_view(),
        name="preferences",
    ),
]
