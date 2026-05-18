from django.urls import path
from django.views.generic import RedirectView

from .views import unsubscribe

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False), name="notifications_index"),
    path("unsubscribe/<str:token>/", unsubscribe, name="notifications_unsubscribe"),
]
