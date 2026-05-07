from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    AdaptiveExercise,
    ExerciseAttempt,
    GrammarTopic,
    LearningRecommendation,
    Skill,
    SkillMastery,
    StudentLearningProfile,
    UserError,
    UserWeakness,
    WeeklyAssessment,
)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "cefr_level", "is_active", "created_at")
    list_filter = ("category", "cefr_level", "is_active")
    search_fields = ("name", "description")
    fieldsets = (
        (_("Skill"), {"fields": ("name", "category", "cefr_level", "description", "is_active")}),
    )


@admin.register(GrammarTopic)
class GrammarTopicAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "cefr_level", "is_active", "created_at")
    list_filter = ("cefr_level", "is_active")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("related_skills",)


@admin.register(StudentLearningProfile)
class StudentLearningProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "current_cefr_level",
        "theta_score",
        "confidence_score",
        "last_activity_at",
    )
    list_filter = ("current_cefr_level",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SkillMastery)
class SkillMasteryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "skill",
        "mastery_score",
        "attempts_count",
        "correct_count",
        "wrong_count",
        "last_practiced_at",
    )
    list_filter = ("skill__category",)
    search_fields = ("user__username", "user__email", "skill__name")


@admin.register(UserError)
class UserErrorAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "source_type",
        "error_type",
        "skill",
        "grammar_topic",
        "severity",
        "created_at",
    )
    list_filter = ("source_type", "error_type")
    search_fields = ("user__username", "original_text", "corrected_text")
    readonly_fields = ("created_at",)


@admin.register(UserWeakness)
class UserWeaknessAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "skill",
        "grammar_topic",
        "weakness_score",
        "priority_score",
        "status",
        "updated_at",
    )
    list_filter = ("status",)
    search_fields = ("user__username", "skill__name", "grammar_topic__name")


@admin.register(AdaptiveExercise)
class AdaptiveExerciseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "question_type",
        "skill",
        "topic",
        "cefr_level",
        "difficulty_score",
        "generated_by_ai",
        "created_at",
    )
    list_filter = ("question_type", "cefr_level", "generated_by_ai")
    search_fields = ("question", "correct_answer", "skill__name", "topic__name")


@admin.register(ExerciseAttempt)
class ExerciseAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "exercise", "is_correct", "score", "time_spent_seconds", "created_at")
    list_filter = ("is_correct",)
    search_fields = ("user__username",)


@admin.register(WeeklyAssessment)
class WeeklyAssessmentAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "score", "triggered_after_lessons_count", "created_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("user__username",)


@admin.register(LearningRecommendation)
class LearningRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "recommendation_type",
        "title",
        "priority",
        "status",
        "created_at",
    )
    list_filter = ("recommendation_type", "status")
    search_fields = ("user__username", "title", "description")
