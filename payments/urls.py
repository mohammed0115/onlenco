from django.urls import path
from . import views

urlpatterns = [
    path("", views.subscribe, name="subscribe"),
    path("history/", views.payment_history, name="payment_history"),
    path("choose-teacher/", views.choose_teacher, name="choose_teacher"),
]
