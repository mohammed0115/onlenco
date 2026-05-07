from rest_framework import serializers

from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    GrammarTopic,
    LearningRecommendation,
    Skill,
    SkillMastery,
    StudentLearningProfile,
    UserError,
    UserWeakness,
)


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "category", "cefr_level", "description", "is_active"]


class GrammarTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrammarTopic
        fields = ["id", "name", "slug", "cefr_level", "description"]


class StudentLearningProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentLearningProfile
        fields = [
            "current_cefr_level",
            "theta_score",
            "learning_speed",
            "confidence_score",
            "last_activity_at",
            "metadata",
            "updated_at",
        ]
        read_only_fields = fields


class SkillMasterySerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)

    class Meta:
        model = SkillMastery
        fields = [
            "id",
            "skill",
            "mastery_score",
            "attempts_count",
            "correct_count",
            "wrong_count",
            "last_practiced_at",
        ]
        read_only_fields = fields


class UserErrorSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    grammar_topic = GrammarTopicSerializer(read_only=True)

    class Meta:
        model = UserError
        fields = [
            "id",
            "source_type",
            "original_text",
            "corrected_text",
            "error_type",
            "grammar_topic",
            "skill",
            "severity",
            "explanation",
            "ai_confidence",
            "created_at",
        ]
        read_only_fields = fields


class UserWeaknessSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    grammar_topic = GrammarTopicSerializer(read_only=True)

    class Meta:
        model = UserWeakness
        fields = [
            "id",
            "skill",
            "grammar_topic",
            "weakness_score",
            "frequency",
            "severity_average",
            "recency_score",
            "priority_score",
            "status",
            "updated_at",
        ]
        read_only_fields = fields


class AdaptiveExerciseSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    topic = GrammarTopicSerializer(read_only=True)

    class Meta:
        model = AdaptiveExercise
        fields = [
            "id",
            "topic",
            "skill",
            "cefr_level",
            "difficulty_score",
            "question_type",
            "question",
            "options",
            "explanation",
            "generated_by_ai",
            "created_at",
        ]
        read_only_fields = fields


class ExerciseAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseAttempt
        fields = [
            "id",
            "exercise",
            "user_answer",
            "is_correct",
            "score",
            "time_spent_seconds",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["id", "is_correct", "score", "feedback", "created_at"]


class ExerciseAttemptInputSerializer(serializers.Serializer):
    user_answer = serializers.CharField(allow_blank=True, max_length=2000)
    time_spent_seconds = serializers.IntegerField(min_value=0, default=0)


class LearningRecommendationSerializer(serializers.ModelSerializer):
    related_skill = SkillSerializer(read_only=True)

    class Meta:
        model = LearningRecommendation
        fields = [
            "id",
            "recommendation_type",
            "title",
            "description",
            "priority",
            "related_skill",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AnalyzeTextInputSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=10000)
    source_type = serializers.ChoiceField(
        choices=[
            "writing",
            "quiz",
            "tutor",
            "speaking",
            "exercise",
            "placement",
        ],
        default="writing",
    )


class GenerateExercisesInputSerializer(serializers.Serializer):
    count_per_weakness = serializers.IntegerField(min_value=1, max_value=10, default=3)


class TutorChatInputSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    topic = serializers.CharField(required=False, allow_blank=True, max_length=120)
    message = serializers.CharField(max_length=4000)


class PlacementSubmitInputSerializer(serializers.Serializer):
    q1 = serializers.CharField(allow_blank=True, max_length=200)
    q2 = serializers.CharField(allow_blank=True, max_length=400)
    q3 = serializers.CharField(allow_blank=True, max_length=4000)
    q4 = serializers.CharField(allow_blank=True, max_length=4000)
    q5 = serializers.CharField(allow_blank=True, max_length=10000)
