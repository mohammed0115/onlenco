from django.urls import path

from . import views


urlpatterns = [
    path("", views.dictionary_view, name="dictionary"),
]

