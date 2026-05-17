from django.contrib import admin

from .models import (
    StudentAssignmentSubmission,
    TeacherAssignment,
    TeacherProfile,
    TeacherStudentNote,
)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "specialization", "is_active", "approved_at")
    search_fields = ("user__email", "user__username", "user__profile__full_name", "specialization")
    list_filter = ("is_active",)


@admin.register(TeacherStudentNote)
class TeacherStudentNoteAdmin(admin.ModelAdmin):
    list_display = ("teacher", "student", "course", "visibility", "needs_support", "created_at")
    search_fields = ("teacher__email", "student__email", "course__title", "note")
    list_filter = ("visibility", "needs_support", "created_at")


class StudentAssignmentSubmissionInline(admin.TabularInline):
    model = StudentAssignmentSubmission
    extra = 0


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "teacher", "course", "assignment_type", "due_date", "is_active")
    search_fields = ("title_ar", "title_en", "teacher__email", "course__title")
    list_filter = ("assignment_type", "is_active", "due_date")
    inlines = [StudentAssignmentSubmissionInline]


@admin.register(StudentAssignmentSubmission)
class StudentAssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "status", "score", "submitted_at")
    search_fields = ("assignment__title_ar", "assignment__title_en", "student__email")
    list_filter = ("status", "submitted_at")
