from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _

from .services.student_flow import (
    can_access_course,
    ensure_course_enrollment,
    published_course_queryset,
    published_lesson_queryset,
)


@login_required
def course_detail(request, pk):
    course = get_object_or_404(published_course_queryset(), pk=pk)
    has_access = can_access_course(request.user, course)
    enrollment = ensure_course_enrollment(request.user, course) if has_access else None
    lessons = list(published_lesson_queryset().filter(course=course))

    return render(request, "courses/detail.html", {
        "course": course,
        "lessons": lessons,
        "has_access": has_access,
        "enrollment": enrollment,
    })


@login_required
def course_lesson_detail(request, course_pk, lesson_pk):
    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    if not can_access_course(request.user, course):
        return HttpResponseForbidden(_("An active subscription is required for this course."))

    enrollment = ensure_course_enrollment(request.user, course)
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course),
        pk=lesson_pk,
    )

    return render(request, "courses/lesson_detail.html", {
        "course": course,
        "lesson": lesson,
        "enrollment": enrollment,
        "video": lesson.get_video_embed(),
    })
