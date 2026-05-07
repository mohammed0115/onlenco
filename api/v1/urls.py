from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="api_token_auth"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger_ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("notifications/", include("notifications.api.urls")),
    path("", include("learning_core.api.urls")),
]
