from django.urls import path

from . import views

app_name = "daily_learning"

urlpatterns = [
    path("",          views.daily_plan_view,      name="daily_plan"),
    path("review/",   views.daily_review_view,    name="daily_review"),
    path("challenge/", views.daily_challenge_view, name="daily_challenge"),
    path("items/<int:item_id>/complete/", views.complete_item, name="complete_item"),
    path("complete/", views.complete_plan, name="complete_plan"),
]
