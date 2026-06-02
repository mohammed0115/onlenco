from rest_framework import serializers

from ..models import AIDailyUsageSummary, AIUsageLog, StudentDailyAILimit

# Cost fields that must be hidden from students unless the admin opts in.
COST_FIELDS = ("estimated_cost_usd", "content_generation_cost", "top_model")


class AIUsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIUsageLog
        fields = (
            "id", "usage_date", "created_at", "user", "role", "feature",
            "provider", "model_name", "input_tokens", "output_tokens",
            "total_tokens", "audio_input_seconds", "audio_output_seconds",
            "ai_minutes_used", "estimated_cost_usd", "status", "latency_ms",
        )


class AIDailyUsageSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AIDailyUsageSummary
        fields = "__all__"


class StudentDailyAILimitSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDailyAILimit
        fields = (
            "date", "plan_name", "allowed_minutes", "used_minutes",
            "remaining_minutes", "is_free_first_day", "is_exceeded",
        )


def strip_cost(data):
    """Remove cost fields from a dict / list-of-dicts (for student responses)."""
    if isinstance(data, list):
        return [strip_cost(d) for d in data]
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k not in COST_FIELDS}
    return data
