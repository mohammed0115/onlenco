from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.preference_service import PreferenceService
from .serializers import NotificationPreferenceSerializer


class NotificationPreferencesView(APIView):
    """GET / PATCH the authenticated user's notification preferences."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer

    @extend_schema(responses=NotificationPreferenceSerializer)
    def get(self, request):
        pref = PreferenceService.get_or_create_for(request.user)
        return Response(NotificationPreferenceSerializer(pref).data)

    @extend_schema(
        request=NotificationPreferenceSerializer,
        responses=NotificationPreferenceSerializer,
    )
    def patch(self, request):
        pref = PreferenceService.get_or_create_for(request.user)
        serializer = NotificationPreferenceSerializer(
            pref, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
