from django.urls import path

from . import views


urlpatterns = [
    path("", views.event_list, name="club"),
    path("<int:pk>/", views.event_detail, name="club_event"),
    path("<int:pk>/rsvp/", views.rsvp, name="club_rsvp"),
]

