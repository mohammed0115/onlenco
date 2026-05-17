from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .auth import ObtainExpiringAuthToken

urlpatterns = [
    path("auth/token/", ObtainExpiringAuthToken.as_view(), name="api_token_auth"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger_ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("notifications/", include("notifications.api.urls")),
    path("motivation/", include("motivation.api.urls")),
    path("payments/", include("payments.api.urls")),
    path("exams/", include("exams.api.urls")),
    path("tutor/", include("tutor.api.urls")),
    path("daily-learning/", include("daily_learning.api.urls")),
    path("control/", include("platform_admin.api_urls")),
    path("", include("learning_core.api.urls")),
]
