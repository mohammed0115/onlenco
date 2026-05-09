from django.urls import path

from . import views

app_name = "payments_api"

urlpatterns = [
    path("plans/", views.PaymentPlansView.as_view(), name="plans"),
    path("methods/", views.PaymentMethodsView.as_view(), name="methods"),
    path("submissions/", views.PaymentSubmissionListCreateView.as_view(), name="submissions"),
    path("subscription/", views.CurrentSubscriptionView.as_view(), name="subscription"),
]
