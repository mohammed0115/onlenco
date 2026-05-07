from django.urls import path

from . import views


urlpatterns = [
    path("", views.analytics_dashboard, name="analytics"),
    path("learning/", views.learning_analytics_dashboard, name="learning_analytics"),
]

