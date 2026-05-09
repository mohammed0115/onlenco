from django.contrib import admin

from learning_core.models import AdaptiveExercise

from .models import (
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamBlueprint,
    ExamQuestion,
    QuestionGenerationBatch,
)


# Re-register AdaptiveExercise with the new question-bank-friendly admin.
try:
    admin.site.unregister(AdaptiveExercise)
except admin.sites.NotRegistered:
    pass


@admin.register(AdaptiveExercise)
class AdaptiveExerciseAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "cefr_level", "question_type", "difficulty_score",
                    "quality_score", "generated_by", "is_active", "is_reviewed")
    list_filter = ("cefr_level", "question_type", "generated_by", "is_active",
                   "is_reviewed", "language")
    search_fields = ("code", "question", "correct_answer")
    list_per_page = 50
    raw_id_fields = ("topic", "skill")
    readonly_fields = ("text_hash", "created_at", "updated_at")
    actions = [
        "mark_reviewed", "deactivate",
        "regenerate_explanation", "run_duplicate_check",
    ]

    @admin.action(description="Mark selected as reviewed")
    def mark_reviewed(self, request, queryset):
        n = queryset.update(is_reviewed=True)
        self.message_user(request, f"{n} item(s) marked reviewed.")

    @admin.action(description="Deactivate selected")
    def deactivate(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} item(s) deactivated.")

    @admin.action(description="Regenerate explanation (AI, falls back to default)")
    def regenerate_explanation(self, request, queryset):
        from .services.ai_question_generator import generate as ai_generate
        regenerated = fallback = 0
        for item in queryset.iterator():
            new_text = ""
            try:
                ai_items = ai_generate(
                    cefr_level=item.cefr_level or "B1",
                    skill=(item.skill.category if item.skill_id and item.skill else "grammar"),
                    count=1,
                    question_type=item.question_type or "multiple_choice",
                    code_prefix=f"adminregen:{item.pk}",
                )
                if ai_items and ai_items[0].get("explanation"):
                    new_text = ai_items[0]["explanation"]
            except Exception:
                pass
            if not new_text:
                new_text = (
                    f"The correct answer is '{item.correct_answer}'. "
                    f"Review the {item.cefr_level or 'CEFR'} guideline for this item."
                )
                fallback += 1
            else:
                regenerated += 1
            AdaptiveExercise.objects.filter(pk=item.pk).update(explanation=new_text)
        self.message_user(
            request,
            f"Regenerated {regenerated} via AI, {fallback} via fallback "
            f"(total {regenerated + fallback}).",
        )

    @admin.action(description="Run duplicate check on selected")
    def run_duplicate_check(self, request, queryset):
        from .services.duplicate_detection import (
            find_near_duplicates, hash_text, normalise_text,
        )
        rehashed = exact_dupes = near_dupes = 0
        for item in queryset.iterator():
            new_hash = hash_text((item.question or "") + "|" + (item.correct_answer or ""))
            if new_hash != item.text_hash:
                AdaptiveExercise.objects.filter(pk=item.pk).update(text_hash=new_hash)
                rehashed += 1
            collisions = (
                AdaptiveExercise.objects
                .filter(text_hash=new_hash)
                .exclude(pk=item.pk)
                .count()
            )
            if collisions:
                exact_dupes += 1
            try:
                if find_near_duplicates(item, limit=1):
                    near_dupes += 1
            except Exception:
                pass
        self.message_user(
            request,
            f"Duplicate check: rehashed {rehashed}, exact-dup matches {exact_dupes}, "
            f"near-dup matches {near_dupes}.",
        )


@admin.register(ExamBlueprint)
class ExamBlueprintAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "exam_type", "cefr_level", "skill",
                    "total_questions", "passing_score", "is_active")
    list_filter = ("exam_type", "cefr_level", "is_active", "skill")
    search_fields = ("name",)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "exam_type", "cefr_level", "total_questions",
                    "is_adaptive", "is_active", "created_at")
    list_filter = ("exam_type", "cefr_level", "is_adaptive", "is_active")
    search_fields = ("title",)
    raw_id_fields = ("blueprint",)


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "exam", "question", "order", "points")
    raw_id_fields = ("exam", "question")


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "exam", "status", "percentage", "passed",
                    "started_at", "submitted_at")
    list_filter = ("status", "passed")
    search_fields = ("user__email", "user__username")
    raw_id_fields = ("user", "exam")
    readonly_fields = ("started_at",)


@admin.register(ExamAnswer)
class ExamAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "attempt", "question", "is_correct", "score", "created_at")
    list_filter = ("is_correct",)
    raw_id_fields = ("attempt", "question")


@admin.register(QuestionGenerationBatch)
class QuestionGenerationBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_id", "status", "cefr_level", "skill",
                    "generated_count", "target_count", "duplicate_count",
                    "started_at", "completed_at")
    list_filter = ("status", "cefr_level", "skill")
    search_fields = ("batch_id",)
    readonly_fields = ("started_at", "completed_at")
