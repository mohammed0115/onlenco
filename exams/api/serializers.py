from rest_framework import serializers

from learning_core.models import AdaptiveExercise

from ..models import (
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamBlueprint,
    ExamQuestion,
)


class ExamBlueprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamBlueprint
        fields = [
            "id", "name", "exam_type", "cefr_level", "skill",
            "total_questions", "duration_minutes", "passing_score",
            "difficulty_distribution", "skill_distribution",
            "question_type_distribution", "is_active",
        ]


class _BankItemSerializer(serializers.ModelSerializer):
    """Trimmed view of AdaptiveExercise for in-flight exam delivery —
    no `correct_answer` exposed to students."""

    class Meta:
        model = AdaptiveExercise
        fields = [
            "id", "code", "cefr_level", "question_type", "question",
            "options", "estimated_time_seconds", "metadata",
        ]


class ExamQuestionSerializer(serializers.ModelSerializer):
    question = _BankItemSerializer(read_only=True)

    class Meta:
        model = ExamQuestion
        fields = ["order", "points", "question"]


class ExamSerializer(serializers.ModelSerializer):
    questions = ExamQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id", "title", "exam_type", "cefr_level", "skill",
            "total_questions", "duration_minutes",
            "is_adaptive", "is_active", "questions", "created_at",
        ]


class AssembleRequestSerializer(serializers.Serializer):
    exam_type = serializers.CharField()
    cefr_level = serializers.CharField()
    skill = serializers.CharField(required=False, allow_blank=True, default="")
    adaptive = serializers.BooleanField(required=False, default=False)


class ExamAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAttempt
        fields = [
            "id", "exam", "started_at", "submitted_at", "score",
            "percentage", "passed", "status", "cefr_result", "feedback",
        ]
        read_only_fields = ["score", "percentage", "passed", "status",
                            "cefr_result", "feedback", "submitted_at"]


class SubmitAnswersSerializer(serializers.Serializer):
    answers = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField(allow_blank=True)),
    )


class ExamAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAnswer
        fields = ["id", "question", "user_answer", "is_correct", "score",
                  "feedback", "created_at"]


class QuestionBankStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    reviewed = serializers.IntegerField()
    by_cefr = serializers.DictField(child=serializers.IntegerField())
    by_skill = serializers.DictField(child=serializers.IntegerField())
    by_question_type = serializers.DictField(child=serializers.IntegerField())
    by_generated_by = serializers.DictField(child=serializers.IntegerField())
    avg_quality_score = serializers.FloatField()
