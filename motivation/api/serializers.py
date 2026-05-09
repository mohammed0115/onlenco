from rest_framework import serializers

from motivation.models import (
    Achievement,
    Challenge,
    ChallengeProgress,
    LeaderboardEntry,
    MotivationMessage,
    UserAchievement,
    UserBadge,
    UserXP,
)


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = [
            "code", "title", "title_ar", "description", "description_ar",
            "kind", "metric", "target_value", "xp_reward",
            "start_at", "end_at",
        ]


class ChallengeProgressSerializer(serializers.ModelSerializer):
    challenge = ChallengeSerializer(read_only=True)
    completed = serializers.SerializerMethodField()
    percent = serializers.SerializerMethodField()

    class Meta:
        model = ChallengeProgress
        fields = ["id", "challenge", "current_value", "completed", "percent", "completed_at"]

    def get_completed(self, obj) -> bool:
        return obj.completed_at is not None

    def get_percent(self, obj) -> int:
        target = obj.challenge.target_value or 1
        return max(0, min(100, int(round((obj.current_value or 0) / target * 100))))


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardEntry
        fields = ["rank", "display_name", "xp", "period", "period_start", "period_end"]


class UserXPSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserXP
        fields = [
            "total_xp",
            "weekly_xp",
            "monthly_xp",
            "level_number",
            "weekly_xp_reset_at",
            "monthly_xp_reset_at",
            "updated_at",
        ]


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = [
            "code",
            "name",
            "name_ar",
            "description",
            "description_ar",
            "category",
            "xp_reward",
            "badge_icon",
        ]


class UserAchievementSerializer(serializers.ModelSerializer):
    achievement = AchievementSerializer(read_only=True)

    class Meta:
        model = UserAchievement
        fields = ["id", "achievement", "earned_at"]


class UserBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBadge
        fields = ["id", "badge_code", "badge_name", "description", "earned_at"]


class MotivationMessageSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    class Meta:
        model = MotivationMessage
        fields = [
            "id",
            "message_type",
            "title",
            "message",
            "language",
            "tone",
            "status",
            "sent_via",
            "created_at",
        ]

    def _humanize(self, value, language):
        # Local import keeps the serializer cheap to import in routes that
        # never touch the humanizer.
        from core.services.text_humanizer import humanize_text
        return humanize_text(value, language=language or "en", mode="display")

    def get_title(self, obj) -> str:
        return self._humanize(obj.title, obj.language)

    def get_message(self, obj) -> str:
        return self._humanize(obj.message, obj.language)
