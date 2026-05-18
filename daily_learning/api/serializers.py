from rest_framework import serializers

from ..models import DailyGoal, DailyLearningItem, DailyLearningPlan, DailyLearningResult


class DailyLearningItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyLearningItem
        fields = (
            "id", "item_type", "title", "instructions", "content_text",
            "question", "options", "correct_answer", "explanation",
            "image_url", "audio_url",
            "cefr_level", "skill", "difficulty_score", "order",
            "estimated_minutes", "is_completed", "completed_at",
        )
        read_only_fields = fields


class DailyGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyGoal
        fields = (
            "id", "date", "goal_type", "target_value", "current_value",
            "completed", "reward_xp", "created_at",
        )
        read_only_fields = fields


class DailyLearningPlanSerializer(serializers.ModelSerializer):
    items = DailyLearningItemSerializer(many=True, read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)
    motivation_message = serializers.SerializerMethodField()

    class Meta:
        model = DailyLearningPlan
        fields = (
            "id", "date", "cefr_level", "plan_type", "title", "description",
            "estimated_minutes", "status", "created_at", "completed_at",
            "progress_percent", "motivation_message", "items",
        )
        read_only_fields = fields

    def get_motivation_message(self, obj) -> str:
        return (obj.metadata or {}).get("motivation_message", "")


class DailyLearningResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyLearningResult
        fields = (
            "id", "daily_plan", "completed_items_count", "total_items_count",
            "score", "xp_earned", "streak_updated", "weaknesses_improved",
            "mistakes_reviewed", "created_at",
        )
        read_only_fields = fields
