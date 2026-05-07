from django.urls import path
from . import views

urlpatterns = [
    path("", views.subscribe, name="subscribe"),
    path("history/", views.payment_history, name="payment_history"),
]
