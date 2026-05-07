from django.urls import path

from .views import unsubscribe

urlpatterns = [
    path("unsubscribe/<str:token>/", unsubscribe, name="notifications_unsubscribe"),
]
