"""DRF endpoints for the daily learning engine.

All endpoints require an authenticated user and only ever return /
mutate that user's own data — there is no admin-level surface here.
Admin tooling lives in the Django admin.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from ..models import DailyLearningItem, DailyLearningPlan
from ..services import daily_plan_generator, daily_progress_service
from .serializers import (
    DailyLearningItemSerializer,
    DailyLearningPlanSerializer,
    DailyLearningResultSerializer,
)


class TodayPlanView(APIView):
    """GET /api/v1/daily-learning/today/ → today's plan for the current user.

    If no plan exists yet for today, one is generated transparently.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DailyLearningPlanSerializer

    @extend_schema(responses=DailyLearningPlanSerializer)
    def get(self, request):
        on_date = timezone.localdate()
        plan = DailyLearningPlan.objects.filter(
            user=request.user, date=on_date,
        ).prefetch_related("items").first()
        if not plan:
            plan = daily_plan_generator.generate_for_user(request.user, on_date=on_date)
        ser = DailyLearningPlanSerializer(plan)
        return Response(ser.data)


class CompleteItemView(APIView):
    """POST /api/v1/daily-learning/items/{id}/complete/"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DailyLearningItemSerializer

    @extend_schema(request=None, responses=DailyLearningItemSerializer)
    def post(self, request, item_id: int):
        item = get_object_or_404(
            DailyLearningItem.objects.select_related("daily_plan"),
            id=item_id,
            daily_plan__user=request.user,
        )
        answer = (request.data.get("answer") or "").strip()
        daily_progress_service.mark_item_complete(item, user_answer=answer)
        return Response(DailyLearningItemSerializer(item).data)


class CompletePlanView(APIView):
    """POST /api/v1/daily-learning/complete/ → finalize the plan."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DailyLearningResultSerializer

    @extend_schema(request=None, responses=DailyLearningResultSerializer)
    def post(self, request):
        on_date = timezone.localdate()
        plan = DailyLearningPlan.objects.filter(
            user=request.user, date=on_date,
        ).first()
        if not plan:
            return Response(
                {"detail": "No plan for today."},
                status=status.HTTP_404_NOT_FOUND,
            )
        force = str(request.data.get("force", "0")) in ("1", "true", "True")
        result = daily_progress_service.complete_plan(plan, force=force)
        return Response(DailyLearningResultSerializer(result).data)


class DailyPlanHistoryViewSet(ReadOnlyModelViewSet):
    """GET /api/v1/daily-learning/history/ → past plans for this user."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DailyLearningPlanSerializer
    queryset = DailyLearningPlan.objects.none()

    def get_queryset(self):
        return (
            DailyLearningPlan.objects
            .filter(user=self.request.user)
            .prefetch_related("items")
            .order_by("-date")
        )
