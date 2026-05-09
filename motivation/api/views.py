from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from motivation.models import (
    Challenge,
    ChallengeProgress,
    LeaderboardEntry,
    MotivationMessage,
    UserAchievement,
    UserBadge,
    UserXP,
)
from motivation.services import (
    challenge_service,
    leaderboard_service,
    streak_service,
)
from motivation.services.motivation_engine import run_for_user

from .serializers import (
    ChallengeProgressSerializer,
    LeaderboardEntrySerializer,
    MotivationMessageSerializer,
    UserAchievementSerializer,
    UserBadgeSerializer,
    UserXPSerializer,
)


class MotivationXPView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserXPSerializer

    @extend_schema(responses=UserXPSerializer)
    def get(self, request):
        xp, _ = UserXP.objects.get_or_create(user=request.user)
        data = UserXPSerializer(xp).data
        data["current_streak"] = streak_service.get_current_streak(request.user)
        data["next_milestone"] = streak_service.upcoming_milestone(data["current_streak"])
        return Response(data)


class MotivationAchievementsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserAchievementSerializer

    def get_queryset(self):
        return (
            UserAchievement.objects
            .filter(user=self.request.user)
            .select_related("achievement")
            .order_by("-earned_at")
        )


class MotivationBadgesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserBadgeSerializer

    def get_queryset(self):
        return UserBadge.objects.filter(user=self.request.user).order_by("-earned_at")


class MotivationMessagesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MotivationMessageSerializer

    def get_queryset(self):
        qs = MotivationMessage.objects.filter(user=self.request.user)
        message_type = self.request.query_params.get("type")
        if message_type:
            qs = qs.filter(message_type=message_type)
        return qs.order_by("-created_at")


class ChallengesView(generics.ListAPIView):
    """Active challenges + this user's progress on each."""
    permission_classes = [IsAuthenticated]
    serializer_class = ChallengeProgressSerializer

    def get_queryset(self):
        active_codes = [c.code for c in challenge_service.open_challenges(self.request.user)]
        # Tick first so the list is fresh, then read.
        try:
            challenge_service.tick_for_user(self.request.user)
        except Exception:
            pass
        return (
            ChallengeProgress.objects
            .filter(user=self.request.user, challenge__code__in=active_codes)
            .select_related("challenge")
            .order_by("challenge__end_at", "challenge__kind")
        )


class LeaderboardView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LeaderboardEntrySerializer

    def get_queryset(self):
        period = self.request.query_params.get("period", "weekly")
        if period not in ("weekly", "monthly"):
            period = "weekly"
        n = int(self.request.query_params.get("limit", "10"))
        return leaderboard_service.top_n(period, n=max(1, min(100, n)))


class MotivationRunView(APIView):
    """Run the engine for the requesting user (rate-limited by DRF defaults).

    Useful for the dashboard widget after a fresh activity, so the user
    sees XP/streak update without waiting for the nightly cron.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserXPSerializer

    @extend_schema(request=None, responses=UserXPSerializer)
    def post(self, request):
        try:
            res = run_for_user(request.user)
            return Response({"ok": True, **res})
        except Exception as e:
            return Response({"ok": False, "error": str(e)}, status=500)
