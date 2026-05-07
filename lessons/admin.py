from django.contrib import admin

from .models import Lesson, LessonProgress, Question, Quiz


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "skill", "level", "duration_minutes", "sort_order", "created_at")
    list_filter = ("skill", "level")
    search_fields = ("title", "description")
    list_editable = ("sort_order",)
    ordering = ("sort_order", "level")


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ("sort_order", "prompt", "choice_a", "choice_b", "choice_c", "choice_d", "correct")
    ordering = ("sort_order", "id")


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("lesson", "pass_score", "question_count")
    inlines = [QuestionInline]

    @admin.display(description="Questions")
    def question_count(self, obj):
        return obj.questions.count()


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "lesson", "video_completed", "quiz_score", "quiz_passed", "completed_at")
    list_filter = ("video_completed", "quiz_passed")
    search_fields = ("user__email", "lesson__title")
    readonly_fields = (
        "user",
        "lesson",
        "video_completed",
        "quiz_score",
        "quiz_passed",
        "last_attempt_at",
        "completed_at",
    )
