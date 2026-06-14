"""Student-facing course discovery and access helpers.

Architecture: the `courses` app is the student learning source of truth.
The legacy `lessons` app remains available for older URLs/quizzes, but new
dashboard recommendations and course visibility are derived from Course,
CourseLevel, CourseUnit, Lesson, LessonQuiz, and CourseEnrollment here.
"""
from __future__ import annotations

from django.db.models import Count, Q
from django.urls import reverse

from courses.models import Course, CourseEnrollment, Lesson


CEFR_ORDER = ("A0", "A1", "A2", "B1", "B2", "C1", "C2", "C3")
BEGINNER_LEVELS = ("A0", "A1")


def current_level_for_user(user) -> str:
    """Return the best current CEFR level known for a student."""
    try:
        learning_profile = getattr(user, "learning_profile", None)
    except Exception:
        learning_profile = None
    current = getattr(learning_profile, "current_cefr_level", "") or ""
    if current in CEFR_ORDER:
        return current

    profile = getattr(user, "profile", None)
    current = getattr(profile, "cefr_level", "") or ""
    if current not in CEFR_ORDER:
        return ""
    return current


def levels_up_to(level_code: str) -> tuple[str, ...]:
    """Every CEFR level from A0 up to (and including) ``level_code``.

    A student placed at B1 should see — and, when subscribed, open — every
    course from A0 through B1. Returns ``()`` for an unknown code.
    """
    if level_code not in CEFR_ORDER:
        return ()
    return CEFR_ORDER[: CEFR_ORDER.index(level_code) + 1]


def visible_level_codes_for_user(user) -> tuple[str, ...]:
    """Return the CEFR levels the student may see on the dashboard.

    Order of precedence:
      1. If the student is **enrolled** across two or more CEFR levels,
         show all of those levels (preview / all-access accounts).
      2. Beginners on the `beginner_start` onboarding path with no level
         yet (or A0) see A0+A1, so they can taste both.
      3. Otherwise show **every level from A0 up to the student's current
         CEFR level** — a B1 student sees A0, A1, A2, B1. This mirrors
         the access rule in :func:`can_access_course`.
    """
    enrolled_levels = set(
        Course.objects
        .filter(enrollments__user=user, status="published",
                is_active=True, level__is_active=True)
        .values_list("level__code", flat=True)
        .distinct()
    )
    profile = getattr(user, "profile", None)
    current = current_level_for_user(user)
    if getattr(profile, "onboarding_path", "") == "beginner_start" and current in ("A0", ""):
        base = set(BEGINNER_LEVELS)
    elif current:
        base = set(levels_up_to(current))
    else:
        base = {"A0"}
    # Admin-assigned (enrolled) courses widen what the student sees, even when
    # their level is below them — so an A0 student assigned A1/B1 sees those too.
    base |= enrolled_levels
    return tuple(c for c in CEFR_ORDER if c in base)


def published_lesson_queryset():
    """Published course lessons visible to students."""
    return (
        Lesson.objects
        .filter(status="published", is_active=True)
        .select_related("course", "unit")
        .prefetch_related("resources")
        .order_by("unit__order", "order", "id")
    )


def published_course_queryset():
    """Published active courses visible to students."""
    return (
        Course.objects
        .filter(status="published", is_active=True, level__is_active=True)
        .select_related("level", "teacher")
        .annotate(
            published_lessons_count=Count(
                "lessons",
                filter=Q(lessons__status="published", lessons__is_active=True),
                distinct=True,
            )
        )
    )


def visible_course_queryset_for_user(user):
    """Published, active courses matching the student's allowed levels."""
    level_codes = visible_level_codes_for_user(user)
    qs = published_course_queryset()
    if not level_codes:
        return qs.none()
    return qs.filter(level__code__in=level_codes)


def can_access_course(user, course: Course) -> bool:
    """Free courses are open. Paid courses require an active subscription AND
    sit at or below the student's placement level — a student placed at B1
    can open every course from A0 through B1, but B2/C1/C2 stay locked until
    they level up. A subscribed student with no placement yet is not
    restricted (they'll be placed soon)."""
    if course.is_free:
        return True
    profile = getattr(user, "profile", None)
    if not (profile and profile.is_subscribed):
        return False
    # An admin-assigned (enrolled) course is always open to a subscribed
    # student, regardless of placement level — the assignment IS the grant.
    # Guard on a real pk so non-persisted / stub course objects don't crash.
    course_pk = getattr(course, "pk", None)
    if course_pk is not None and CourseEnrollment.objects.filter(
            user=user, course_id=course_pk).exists():
        return True
    current = current_level_for_user(user)
    code = None
    if getattr(course, "level_id", None):
        code = getattr(getattr(course, "level", None), "code", None)
    if not current or code not in CEFR_ORDER:
        return True
    return CEFR_ORDER.index(code) <= CEFR_ORDER.index(current)


def can_access_lesson(user, lesson: Lesson) -> bool:
    """Per-lesson access = the lesson's override, falling back to its course.

    An admin can pin a single lesson ``free`` (always open) or ``locked``
    (always needs a subscription); otherwise the lesson inherits the
    course's free/paid rule via :func:`can_access_course`.
    """
    override = getattr(lesson, "access_override", Lesson.ACCESS_INHERIT)
    if override == Lesson.ACCESS_FREE:
        return True
    if override == Lesson.ACCESS_LOCKED:
        profile = getattr(user, "profile", None)
        return bool(profile and profile.is_subscribed)
    course = getattr(lesson, "course", None)
    return can_access_course(user, course) if course is not None else False


def next_sequential_lesson_for_user(user):
    """The student's next lesson to practice for the daily challenge.

    Picks the course matching the student's CEFR level (A0 → onlenco-beginner,
    A1 → elementary, …), then the first lesson they have NOT completed yet,
    ordered by lesson order — so day 1 lands on lesson 1, day 2 on lesson 2,
    and so on as each lesson is completed. Returns ``None`` when no course is
    visible. Falls back to onlenco-beginner if the level has no match.
    """
    from courses.models import CourseLessonProgress

    course = (
        visible_course_queryset_for_user(user)
        .order_by("level__order", "level__code")
        .first()
    )
    if course is None:
        course = published_course_queryset().filter(slug="onlenco-beginner").first()
    if course is None:
        return None

    lessons = list(published_lesson_queryset().filter(course=course))
    if not lessons:
        return None
    completed_ids = set(
        CourseLessonProgress.objects
        .filter(user=user, lesson__in=lessons, completed_at__isnull=False)
        .values_list("lesson_id", flat=True)
    )
    for lesson in lessons:
        if lesson.id not in completed_ids:
            return lesson
    return lessons[-1]   # everything done → let them replay the last one


def ensure_course_enrollment(user, course: Course) -> CourseEnrollment:
    """Create the student's enrollment row once they enter an accessible course."""
    enrollment, _ = CourseEnrollment.objects.get_or_create(
        user=user,
        course=course,
        defaults={"status": "active"},
    )
    return enrollment


def dashboard_courses_for_user(user, *, limit: int = 12) -> list[Course]:
    """Return dashboard-ready courses matched to the student's CEFR level."""
    qs = (
        visible_course_queryset_for_user(user)
        .order_by("level__order", "level__code", "title")
    )
    if limit:
        qs = qs[:limit]

    courses = list(qs)
    enrollments = {
        enrollment.course_id: enrollment
        for enrollment in CourseEnrollment.objects.filter(user=user, course__in=courses)
    }
    for course in courses:
        course.student_enrollment = enrollments.get(course.id)
        course.student_has_access = can_access_course(user, course)
    return courses


def first_published_course_for_levels(level_codes: tuple[str, ...] | list[str]) -> Course | None:
    """Return the first published course in a CEFR set."""
    if not level_codes:
        return None
    return (
        published_course_queryset()
        .filter(level__code__in=level_codes)
        .order_by("level__order", "level__code", "title", "id")
        .first()
    )


def first_beginner_course() -> Course | None:
    """Return the first beginner course a new learner should start.

    A0 is preferred over A1 when both have published courses — a true
    beginner should not silently land on A1 just because A0 has fewer
    courses or none are seeded yet."""
    a0 = first_published_course_for_levels(("A0",))
    if a0 is not None:
        return a0
    return first_published_course_for_levels(BEGINNER_LEVELS)


def first_published_lesson_for_course(course: Course | None) -> Lesson | None:
    """Return the next lesson candidate for a course."""
    if course is None:
        return None
    return published_lesson_queryset().filter(course=course).first()


def _visible_recommended_course_from_metadata(user) -> Course | None:
    """Resolve a LearningRecommendation metadata course id, if still visible."""
    try:
        from learning_core.models import LearningRecommendation
    except Exception:
        return None

    recommendations = (
        LearningRecommendation.objects
        .filter(user=user, recommendation_type="continue_lesson")
        .exclude(status__in=["dismissed", "replaced"])
        .order_by("-priority", "-created_at")
    )
    visible_ids = set(visible_course_queryset_for_user(user).values_list("id", flat=True))
    for recommendation in recommendations:
        course_id = (recommendation.metadata or {}).get("course_id")
        if course_id in visible_ids:
            return (
                published_course_queryset()
                .filter(id=course_id)
                .first()
            )
    return None


def recommended_course_for_user(user) -> Course | None:
    """Return the current recommended visible course for a student."""
    metadata_course = _visible_recommended_course_from_metadata(user)
    if metadata_course:
        return metadata_course
    return (
        visible_course_queryset_for_user(user)
        .order_by("level__order", "level__code", "title", "id")
        .first()
    )


def quiz_status_for_lesson(lesson: Lesson | None) -> dict:
    """Summarise quiz availability without exposing questions/answers."""
    if lesson is None:
        return {"state": "none", "label": "No quiz"}
    try:
        quiz = lesson.quiz
    except Exception:
        return {"state": "none", "label": "No quiz"}
    if not quiz.is_active:
        return {"state": "inactive", "label": "Quiz unavailable"}
    question_count = quiz.questions.count()
    if question_count == 0:
        return {"state": "empty", "label": "Quiz pending"}
    return {
        "state": "available",
        "label": "Quiz ready",
        "passing_score": quiz.passing_score,
        "question_count": question_count,
    }


def dashboard_learning_plan_for_user(user) -> dict:
    """Return the dashboard's current course, next lesson, and progress."""
    course = recommended_course_for_user(user)
    lesson = first_published_lesson_for_course(course)
    enrollment = None
    has_access = False
    continue_url = ""
    if course:
        enrollment = (
            CourseEnrollment.objects
            .filter(user=user, course=course)
            .order_by("-enrolled_at")
            .first()
        )
        has_access = can_access_course(user, course)
        if lesson and has_access:
            continue_url = reverse("courses:lesson_detail", args=[course.pk, lesson.pk])
        else:
            continue_url = reverse("courses:course_detail", args=[course.pk])

    return {
        "current_level": current_level_for_user(user),
        "visible_level_codes": visible_level_codes_for_user(user),
        "recommended_course": course,
        "recommended_lesson": lesson,
        "continue_url": continue_url,
        "progress_percentage": (
            enrollment.progress_percentage if enrollment else 0.0
        ),
        "quiz_status": quiz_status_for_lesson(lesson),
        "has_access": has_access,
    }


def ensure_course_recommendation(user, course: Course | None, *, source: str) -> None:
    """Create/update a LearningRecommendation pointing at a visible course."""
    if course is None:
        return
    lesson = first_published_lesson_for_course(course)
    try:
        from learning_core.models import LearningRecommendation
    except Exception:
        return

    metadata = {
        "source": source,
        "course_id": course.id,
        "course_level": course.level.code,
    }
    if lesson:
        metadata["lesson_id"] = lesson.id

    LearningRecommendation.objects.update_or_create(
        user=user,
        recommendation_type="continue_lesson",
        metadata__source=source,
        defaults={
            "title": f"Continue {course.title}",
            "description": (
                f"Your next course at {course.level.code} is ready."
                if lesson else
                f"A {course.level.code} course is ready for you."
            ),
            "priority": 100.0,
            "status": "pending",
            "metadata": metadata,
        },
    )


def seed_beginner_course_recommendation(user) -> None:
    """Recommend the first A0/A1 course for beginner onboarding."""
    ensure_course_recommendation(
        user,
        first_beginner_course(),
        source="beginner_onboarding",
    )


def seed_level_course_recommendation(user, level: str, *, source: str = "placement") -> None:
    """Recommend the first published course at a placement/current level."""
    if level not in CEFR_ORDER:
        return
    ensure_course_recommendation(
        user,
        first_published_course_for_levels((level,)),
        source=source,
    )
