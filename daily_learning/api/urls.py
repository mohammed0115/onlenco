from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("history", views.DailyPlanHistoryViewSet, basename="daily-learning-history")

urlpatterns = [
    path("today/", views.TodayPlanView.as_view(), name="daily-learning-today"),
    path("items/<int:item_id>/complete/", views.CompleteItemView.as_view(),
         name="daily-learning-complete-item"),
    path("complete/", views.CompletePlanView.as_view(), name="daily-learning-complete-plan"),
    path("", include(router.urls)),
]
