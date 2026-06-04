"""Admin classes with role-aware filtering.

Key rule: a Teacher only ever sees / can change rows tied to their own
courses. Academic Admins see everything. The filtering happens in
`get_queryset` + `has_change_permission(obj)` so it's enforced both in
the list view AND on the change form.
"""
from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.translation import gettext_lazy as _

from . import permissions as perms
from .models import (
    AdminActionLog, ContentReviewLog, Course, CourseEnrollment,
    CourseLevel, CourseUnit, DigitalCertificate, Lesson, LessonQuestion, LessonQuiz,
    LessonResource,
)
from .services import review_workflow


@admin.register(DigitalCertificate)
class DigitalCertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_uuid", "student", "course", "level", "average_score", "issued_by", "issued_at")
    search_fields = ("certificate_uuid", "student__email", "student__username", "course__title")
    list_filter = ("level", "issued_at")
    readonly_fields = ("certificate_uuid", "issued_at")
from .services.admin_log import log_admin_action


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class CourseUnitInline(admin.TabularInline):
    model = CourseUnit
    extra = 0
    fields = ("title", "order", "description")


class LessonResourceInline(admin.TabularInline):
    model = LessonResource
    extra = 0
    fields = ("resource_type", "title", "file", "url", "order")


class LessonQuestionInline(admin.TabularInline):
    model = LessonQuestion
    extra = 0
    fields = ("question_type", "question_text", "options",
              "correct_answer", "points", "order")


# ---------------------------------------------------------------------------
# CourseLevel
# ---------------------------------------------------------------------------

@admin.register(CourseLevel)
class CourseLevelAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("order", "code")


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "teacher", "status", "language",
                    "is_active", "created_at")
    list_filter = ("status", "level", "language", "is_active")
    search_fields = ("title", "description", "teacher__email", "teacher__username")
    raw_id_fields = ("teacher", "created_by", "reviewed_by")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CourseUnitInline]
    actions = ["submit_for_review_action", "approve_action",
               "reject_action", "publish_action", "archive_action"]
    readonly_fields = ("created_by", "reviewed_by", "reviewed_at",
                       "created_at", "updated_at")

    # ---- queryset / object-level perms -------------------------------

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return perms.filter_courses_for(request.user, qs)

    def has_change_permission(self, request, obj=None):
        base = super().has_change_permission(request, obj)
        if not base:
            return False
        if obj is None:
            return True
        return perms.can_edit_course(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        # Teachers can't delete; only Academic Admins (and superusers).
        if not perms.is_academic_admin(request.user):
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj) or [])
        # Status is teacher-controllable for `submit_for_review` only via
        # the action; direct edits are admin-only.
        if not perms.can_publish_course(request.user, obj):
            ro.extend(["status", "reviewed_by", "reviewed_at"])
        return ro

    # ---- save_model — stamp created_by + log -------------------------

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        log_admin_action(
            admin_user=request.user,
            action_type="course.create" if not change else "course.update",
            description=f"{'Created' if not change else 'Updated'} course '{obj.title}'",
            metadata={"course_id": obj.id, "status": obj.status},
        )

    # ---- bulk actions ------------------------------------------------

    @admin.action(description=_("Submit selected for review"))
    def submit_for_review_action(self, request, queryset):
        n = 0
        for course in queryset:
            if not perms.can_edit_course(request.user, course):
                continue
            review_workflow.submit_for_review(
                content_object=course, submitted_by=request.user,
            )
            n += 1
        self.message_user(request, _("%d course(s) submitted for review.") % n)

    @admin.action(description=_("Approve selected (publishes)"))
    def approve_action(self, request, queryset):
        if not perms.can_review_content(request.user):
            self.message_user(request, _("Only Academic Admins can approve."),
                              level=messages.ERROR)
            return
        for course in queryset:
            review_workflow.approve(content_object=course, reviewed_by=request.user)
        self.message_user(request, _("%d course(s) approved & published.") % queryset.count())

    @admin.action(description=_("Reject selected"))
    def reject_action(self, request, queryset):
        if not perms.can_review_content(request.user):
            self.message_user(request, _("Only Academic Admins can reject."),
                              level=messages.ERROR)
            return
        notes = "Rejected via bulk action."
        for course in queryset:
            review_workflow.reject(content_object=course, reviewed_by=request.user,
                                   notes=notes)
        self.message_user(request, _("%d course(s) rejected.") % queryset.count())

    @admin.action(description=_("Publish selected (Academic Admin only)"))
    def publish_action(self, request, queryset):
        if not perms.is_academic_admin(request.user):
            self.message_user(request, _("Permission denied."), level=messages.ERROR)
            return
        n = queryset.update(status="published")
        log_admin_action(admin_user=request.user, action_type="course.publish",
                         description=f"Published {n} course(s)",
                         metadata={"count": n})
        self.message_user(request, _("%d course(s) published.") % n)

    @admin.action(description=_("Archive selected"))
    def archive_action(self, request, queryset):
        if not perms.is_academic_admin(request.user):
            self.message_user(request, _("Permission denied."), level=messages.ERROR)
            return
        n = queryset.update(status="archived", is_active=False)
        log_admin_action(admin_user=request.user, action_type="course.archive",
                         description=f"Archived {n} course(s)")
        self.message_user(request, _("%d course(s) archived.") % n)


# ---------------------------------------------------------------------------
# CourseUnit (also reachable directly)
# ---------------------------------------------------------------------------

@admin.register(CourseUnit)
class CourseUnitAdmin(admin.ModelAdmin):
    list_display = ("course", "title", "order")
    list_filter = ("course__level",)
    search_fields = ("title", "course__title")
    raw_id_fields = ("course",)


# ---------------------------------------------------------------------------
# Lesson
# ---------------------------------------------------------------------------

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "cefr_level", "skill", "lesson_type",
                    "status", "created_by", "created_at")
    list_filter = ("status", "lesson_type", "cefr_level", "skill",
                   "course__level", "course")
    search_fields = ("title", "content_html", "course__title")
    raw_id_fields = ("course", "unit", "created_by", "reviewed_by")
    inlines = [LessonResourceInline]
    actions = ["submit_for_review_action", "approve_action",
               "reject_action", "duplicate_action"]
    readonly_fields = ("created_by", "reviewed_by", "reviewed_at",
                       "created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("course", "unit", "title", "order", "lesson_type",
                       "cefr_level", "skill", "grammar_topic", "vocabulary_topic"),
        }),
        (_("Video"), {
            "fields": ("video_file", "video_url"),
            "description": _(
                "You can either upload a video file <em>or</em> paste a URL "
                "(YouTube, Vimeo, or a direct .mp4/.webm link). If both are "
                "provided, the uploaded file is played first; the URL is "
                "used as a fallback if the file is missing."
            ),
        }),
        (_("Other media"), {
            "fields": ("audio_file", "pdf_file", "transcript"),
            "classes": ("collapse",),
        }),
        (_("Content"), {
            "fields": ("content_html", "duration_minutes", "is_active"),
        }),
        (_("Review"), {
            "fields": ("status", "created_by", "reviewed_by", "reviewed_at",
                       "created_at", "updated_at"),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return perms.filter_lessons_for(request.user, qs)

    def has_change_permission(self, request, obj=None):
        base = super().has_change_permission(request, obj)
        if not base:
            return False
        if obj is None:
            return True
        return perms.can_edit_lesson(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        if not perms.is_academic_admin(request.user):
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj) or [])
        if not perms.can_review_content(request.user):
            ro.extend(["status", "reviewed_by", "reviewed_at"])
        return ro

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        log_admin_action(
            admin_user=request.user,
            action_type="lesson.create" if not change else "lesson.update",
            description=f"{'Created' if not change else 'Updated'} lesson '{obj.title}'",
            metadata={"lesson_id": obj.id, "status": obj.status},
        )

    @admin.action(description=_("Submit selected lessons for review"))
    def submit_for_review_action(self, request, queryset):
        n = 0
        for lesson in queryset:
            if not perms.can_edit_lesson(request.user, lesson):
                continue
            review_workflow.submit_for_review(
                content_object=lesson, submitted_by=request.user,
            )
            n += 1
        self.message_user(request, _("%d lesson(s) submitted for review.") % n)

    @admin.action(description=_("Approve selected lessons"))
    def approve_action(self, request, queryset):
        if not perms.can_review_content(request.user):
            self.message_user(request, _("Only Academic Admins can approve."),
                              level=messages.ERROR)
            return
        for lesson in queryset:
            review_workflow.approve(content_object=lesson, reviewed_by=request.user)
        self.message_user(request, _("%d lesson(s) approved.") % queryset.count())

    @admin.action(description=_("Reject selected lessons"))
    def reject_action(self, request, queryset):
        if not perms.can_review_content(request.user):
            self.message_user(request, _("Only Academic Admins can reject."),
                              level=messages.ERROR)
            return
        for lesson in queryset:
            review_workflow.reject(
                content_object=lesson, reviewed_by=request.user,
                notes="Rejected via bulk action.",
            )
        self.message_user(request, _("%d lesson(s) rejected.") % queryset.count())

    @admin.action(description=_("Duplicate selected lessons"))
    def duplicate_action(self, request, queryset):
        n = 0
        for lesson in queryset:
            if not perms.can_edit_lesson(request.user, lesson):
                continue
            lesson.pk = None
            lesson.title = f"{lesson.title} (copy)"
            lesson.status = "draft"
            lesson.created_by = request.user
            lesson.reviewed_by = None
            lesson.reviewed_at = None
            lesson.save()
            n += 1
        log_admin_action(admin_user=request.user, action_type="lesson.duplicate",
                         description=f"Duplicated {n} lesson(s)")
        self.message_user(request, _("%d lesson(s) duplicated.") % n)


# ---------------------------------------------------------------------------
# Lesson resources / quizzes / questions
# ---------------------------------------------------------------------------

@admin.register(LessonResource)
class LessonResourceAdmin(admin.ModelAdmin):
    list_display = ("lesson", "resource_type", "title", "order")
    list_filter = ("resource_type",)
    search_fields = ("title", "lesson__title")
    raw_id_fields = ("lesson",)


@admin.register(LessonQuiz)
class LessonQuizAdmin(admin.ModelAdmin):
    list_display = ("title", "lesson", "passing_score",
                    "time_limit_minutes", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "lesson__title")
    raw_id_fields = ("lesson",)
    inlines = [LessonQuestionInline]


@admin.register(LessonQuestion)
class LessonQuestionAdmin(admin.ModelAdmin):
    list_display = ("quiz", "question_type", "order", "points",
                    "difficulty_score")
    list_filter = ("question_type",)
    search_fields = ("question_text", "quiz__title")
    raw_id_fields = ("quiz",)


# ---------------------------------------------------------------------------
# Enrollments / review log / admin log
# ---------------------------------------------------------------------------

@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "status", "progress_percentage",
                    "enrolled_at")
    list_filter = ("status", "course__level")
    search_fields = ("user__email", "user__username", "course__title")
    raw_id_fields = ("user", "course")
    readonly_fields = ("enrolled_at",)


@admin.register(ContentReviewLog)
class ContentReviewLogAdmin(admin.ModelAdmin):
    list_display = ("id", "content_type", "object_id", "status",
                    "submitted_by", "reviewed_by", "created_at")
    list_filter = ("status", "content_type")
    search_fields = ("notes",)
    raw_id_fields = ("submitted_by", "reviewed_by")
    readonly_fields = ("content_type", "object_id", "submitted_by",
                       "created_at", "updated_at")


@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "admin_user", "action_type",
                    "target_user", "description")
    list_filter = ("action_type",)
    search_fields = ("description", "admin_user__username",
                     "target_user__username")
    raw_id_fields = ("admin_user", "target_user")
    readonly_fields = ("admin_user", "target_user", "action_type",
                       "description", "metadata", "created_at")

    def has_add_permission(self, request):
        # Audit log is system-written only.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Only superusers can prune the log.
        return getattr(request.user, "is_superuser", False)
