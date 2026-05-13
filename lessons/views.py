from urllib.parse import parse_qs, urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from accounts.decorators import subscription_required

from .models import Lesson, LessonProgress, Quiz


def _to_embed_url(url: str) -> str:
    """Convert common YouTube watch/share URLs to embeddable URLs."""
    if not url:
        return ""
    try:
        if "youtube.com/watch" in url:
            parsed = urlparse(url)
            vid = parse_qs(parsed.query).get("v", [None])[0]
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
        if "youtu.be/" in url:
            vid = url.split("youtu.be/", 1)[1].split("?", 1)[0].split("&", 1)[0].strip("/")
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
    except Exception:
        pass
    return url


@login_required
def dashboard(request):
    """Student dashboard backed by the courses app learning catalog."""

    profile = request.user.profile
    lessons = []

    next_club_event = None
    next_club_rsvp = None
    try:
        from club.models import ClubEvent, ClubRSVP

        next_club_event = (
            ClubEvent.objects.filter(is_published=True, starts_at__gte=timezone.now())
            .order_by("starts_at")
            .first()
        )
        if next_club_event:
            next_club_rsvp = (
                ClubRSVP.objects.filter(event=next_club_event, user=request.user)
                .order_by("-updated_at")
                .first()
            )
    except Exception:
        pass

    last_rejected = None
    try:
        latest = request.user.payment_submissions.order_by("-created_at").first()
        last_rejected = (
            request.user.payment_submissions
            .filter(status="rejected")
            .order_by("-created_at")
            .first()
        )
        if latest and latest.status != "rejected":
            last_rejected = None
    except Exception:
        last_rejected = None

    # Adaptive learning summary (best-effort; tolerates missing data).
    learning_summary = {
        "cefr_level": profile.cefr_level,
        "top_weaknesses": [],
        "recent_errors": [],
        "recommendations": [],
        "exercise_success_rate": None,
        "beginner_first_lesson": None,
    }

    try:
        from learning_core.models import (
            ExerciseAttempt,
            LearningRecommendation,
            StudentLearningProfile,
            UserError,
        )
        from learning_core.services.weakness_engine import get_top_weaknesses

        learning_profile = StudentLearningProfile.objects.filter(user=request.user).first()
        if learning_profile and learning_profile.current_cefr_level:
            learning_summary["cefr_level"] = learning_profile.current_cefr_level
        top = get_top_weaknesses(request.user, limit=3)
        learning_summary["top_weaknesses"] = [
            {
                "label": (
                    (w.grammar_topic.name if w.grammar_topic else None)
                    or (w.skill.name if w.skill else "general")
                ),
                "priority": round(w.priority_score, 1),
            }
            for w in top
        ]
        learning_summary["recent_errors"] = list(
            UserError.objects.filter(user=request.user)
            .order_by("-created_at")
            .values("original_text", "explanation", "error_type", "created_at")[:5]
        )
        learning_summary["recommendations"] = list(
            LearningRecommendation.objects.filter(user=request.user)
            .exclude(status="dismissed")
            .order_by("-priority")
            .values("recommendation_type", "title", "description", "priority")[:5]
        )
        attempts = ExerciseAttempt.objects.filter(user=request.user)
        total = attempts.count()
        if total:
            correct = attempts.filter(is_correct=True).count()
            learning_summary["exercise_success_rate"] = round(correct / total * 100, 1)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Dashboard learning summary failed")

    motivation_widget = _build_motivation_widget(request.user)
    student_courses = []
    learning_plan = {}
    try:
        from courses.services.student_flow import (
            dashboard_courses_for_user,
            dashboard_learning_plan_for_user,
        )
        student_courses = dashboard_courses_for_user(request.user)
        learning_plan = dashboard_learning_plan_for_user(request.user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Dashboard course lookup failed")

    # Surface today's DailyLearningPlan. Always go through the generator
    # — it's idempotent on (user, date) AND will auto-regenerate when
    # the existing plan's CEFR level no longer matches the user's
    # profile (e.g. an A0 learner who briefly had an A2 plan from
    # before the resolver was fixed). The early-return-on-existing
    # short-circuit was the bug that kept stale plans visible.
    today_plan = None
    try:
        from daily_learning.models import DailyLearningPlan
        from daily_learning.services.daily_plan_generator import generate_for_user
        on_date = timezone.localdate()
        try:
            plan = generate_for_user(request.user, on_date=on_date)
            today_plan = (
                DailyLearningPlan.objects
                .filter(id=plan.id)
                .prefetch_related("items")
                .first()
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Daily plan generation on dashboard failed; "
                "falling back to whatever already exists"
            )
            today_plan = DailyLearningPlan.objects.filter(
                user=request.user, date=on_date,
            ).prefetch_related("items").first()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Today's daily plan lookup failed")

    return render(request, "lessons/dashboard.html", {
        "profile": profile,
        "lessons": lessons,
        "student_courses": student_courses,
        "learning_plan": learning_plan,
        "is_subscribed": profile.is_subscribed,
        "next_club_event": next_club_event,
        "next_club_rsvp": next_club_rsvp,
        "last_rejected": last_rejected,
        "learning_summary": learning_summary,
        "motivation": motivation_widget,
        "today_plan": today_plan,
    })


def _build_motivation_widget(user) -> dict:
    """Best-effort widget data; tolerates missing rows."""
    widget = {
        "xp_total": 0,
        "level_number": 1,
        "weekly_xp": 0,
        "current_streak": 0,
        "next_milestone": None,
        "recent_messages": [],
        "recent_achievements": [],
        "badges_count": 0,
        "challenges": [],
        "engagement_score": 0,
        "churn_risk": "low",
        "cefr_progress": {},
    }
    try:
        from motivation.models import (
            MotivationMessage,
            UserAchievement,
            UserBadge,
            UserXP,
        )
        from motivation.services import streak_service

        xp = UserXP.objects.filter(user=user).first()
        if xp:
            widget["xp_total"] = xp.total_xp
            widget["level_number"] = xp.level_number
            widget["weekly_xp"] = xp.weekly_xp

        widget["current_streak"] = streak_service.get_current_streak(user)
        widget["next_milestone"] = streak_service.upcoming_milestone(widget["current_streak"])

        from core.services.text_humanizer import humanize_text

        widget["recent_messages"] = []
        for m in (
            MotivationMessage.objects
            .filter(user=user)
            .order_by("-created_at")
            .values("title", "message", "language", "tone", "message_type", "created_at")[:5]
        ):
            lang = m.get("language") or "en"
            widget["recent_messages"].append({
                **m,
                "title": humanize_text(m["title"], language=lang),
                "message": humanize_text(m["message"], language=lang),
            })
        widget["recent_achievements"] = list(
            UserAchievement.objects
            .filter(user=user)
            .select_related("achievement")
            .order_by("-earned_at")[:5]
        )
        widget["badges_count"] = UserBadge.objects.filter(user=user).count()

        # Active challenges with progress
        try:
            from motivation.models import ChallengeProgress
            from motivation.services import challenge_service
            active_codes = [c.code for c in challenge_service.open_challenges(user)]
            for p in (ChallengeProgress.objects
                      .filter(user=user, challenge__code__in=active_codes)
                      .select_related("challenge")
                      .order_by("challenge__end_at")[:4]):
                target = p.challenge.target_value or 1
                widget["challenges"].append({
                    "title": p.challenge.title,
                    "title_ar": p.challenge.title_ar,
                    "kind": p.challenge.kind,
                    "current": p.current_value,
                    "target": p.challenge.target_value,
                    "percent": max(0, min(100, int(round((p.current_value or 0) / target * 100)))),
                    "completed": p.completed_at is not None,
                })
        except Exception:
            pass

        # Behavior signals + CEFR progress
        try:
            from analytics.services.scoring import engagement_score, churn_risk
            from learning_core.services.adaptive_difficulty import cefr_progress
            from learning_core.models import StudentLearningProfile
            widget["engagement_score"] = engagement_score(user)
            widget["churn_risk"] = churn_risk(user)
            prof = StudentLearningProfile.objects.filter(user=user).first()
            if prof:
                # Pin the displayed band to the user's own Profile so a
                # learner whose theta has drifted out of band still sees
                # their official level (A0 → A1, not A2 → B1). The
                # adaptive engine still updates theta freely behind the
                # scenes; the dashboard just stops misreporting.
                profile_level = getattr(getattr(user, "profile", None), "cefr_level", "") or ""
                widget["cefr_progress"] = cefr_progress(
                    prof.theta_score or 0.0,
                    current_level=profile_level or None,
                )
        except Exception:
            pass
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Motivation widget build failed")
    return widget


@login_required
def lesson_detail(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

    quiz = None
    try:
        quiz = lesson.quiz
    except Quiz.DoesNotExist:
        quiz = None

    return render(request, "lessons/detail.html", {
        "lesson": lesson,
        "progress": progress,
        "quiz": quiz,
        "embed_url": _to_embed_url(lesson.video_url),
        "is_subscribed": request.user.profile.is_subscribed,
    })


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def mark_video_complete(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

    if not progress.video_completed:
        progress.video_completed = True
        if progress.is_complete and not progress.completed_at:
            progress.completed_at = timezone.now()
        progress.save()
        messages.success(request, "Marked as watched.")

    # Fire motivation engine inline so the first video watch awards XP /
    # ticks the streak even when the lesson has no quiz.
    try:
        from motivation.services.motivation_engine import run_for_user
        run_for_user(request.user)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("motivation engine post-video failed",
                                            exc_info=True)

    return redirect("lesson_detail", pk=lesson.pk)


@login_required
@require_http_methods(["GET", "POST"])
@subscription_required(allow_free_tier=True)
def quiz_attempt(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

    try:
        quiz = lesson.quiz
    except Quiz.DoesNotExist:
        quiz = None

    if not quiz:
        raise Http404("Lesson has no quiz")

    questions = list(quiz.questions.all())

    def _choices(q):
        return [
            ("a", q.choice_a),
            ("b", q.choice_b),
            ("c", q.choice_c),
            ("d", q.choice_d),
        ]

    if request.method == "GET":
        return render(request, "lessons/quiz.html", {
            "lesson": lesson,
            "quiz": quiz,
            "questions": questions,
        })

    # POST: grade attempt
    correct_count = 0
    results = []
    for q in questions:
        chosen = (request.POST.get(f"q_{q.id}") or "").strip().lower()
        is_correct = chosen == q.correct
        if is_correct:
            correct_count += 1
        results.append({
            "q": q,
            "chosen": chosen,
            "correct": q.correct,
            "choices": [(k, v) for k, v in _choices(q) if v],
        })

    total = len(questions) or 1
    score = int(correct_count * 100 / total)

    progress.quiz_score = score
    progress.quiz_passed = score >= quiz.pass_score
    if progress.is_complete and not progress.completed_at:
        progress.completed_at = timezone.now()
    progress.save()

    # Best-effort adaptive learning side-effects. Never blocks the user flow.
    weekly_assessment_id = None
    personalised_exercises: list = []
    try:
        from .services.adaptive_quiz_adapter import process_quiz_submission
        summary = process_quiz_submission(request.user, lesson, results)
        weekly_assessment_id = summary.get("weekly_assessment_triggered")
        ex_ids = summary.get("personalised_exercise_ids") or []
        if ex_ids:
            try:
                from learning_core.models import AdaptiveExercise
                personalised_exercises = list(
                    AdaptiveExercise.objects.filter(id__in=ex_ids)
                    .only("id", "question", "cefr_level", "options", "question_type")
                )
            except Exception:
                personalised_exercises = []
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Adaptive quiz adapter failed")

    return render(request, "lessons/quiz_result.html", {
        "lesson": lesson,
        "quiz": quiz,
        "progress": progress,
        "score": score,
        "passed": progress.quiz_passed,
        "results": results,
        "weekly_assessment_id": weekly_assessment_id,
        "personalised_exercises": personalised_exercises,
    })


@login_required
@require_http_methods(["GET"])
def daily_exam(request):
    """Start (or resume) today's daily check-in and redirect to the player.

    Wrapped: any failure inside `start_daily_assessment` (DB hiccup, AI
    generator error not caught by the inner handler, etc.) used to bubble
    up as a generic 500. Catch + log + send the student back to the
    dashboard with a friendly flash so a transient backend issue doesn't
    burn a streak.
    """
    from learning_core.services.weekly_assessment import start_daily_assessment

    try:
        assessment = start_daily_assessment(request.user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "daily_exam: start_daily_assessment failed for user_id=%s",
            request.user.id,
        )
        messages.error(
            request,
            "تعذّر بدء التقييم اليومي الآن، حاول مرة أخرى بعد قليل.",
        )
        return redirect("dashboard")
    return redirect("exam_play", assessment_id=assessment.id)


@login_required
@require_http_methods(["GET", "POST"])
def exam_play(request, assessment_id):
    """Duolingo-style single-page exam player.

    GET  → render the player with all exercises serialised into JS.
    POST → accept JSON: {"answers":[{exercise_id,answer},...]}, grade, finalise.
    Works for both daily and weekly assessments (uses `assessment.kind`).
    """
    from learning_core.models import ExerciseAttempt, WeeklyAssessment
    from learning_core.services.adaptive_difficulty import process_attempt
    from learning_core.services.weekly_assessment import complete

    assessment = get_object_or_404(
        WeeklyAssessment, pk=assessment_id, user=request.user
    )
    exercises = list(assessment.exercises.all())

    if request.method == "POST":
        import json
        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            data = {}
        answers = {int(a.get("exercise_id")): (a.get("answer") or "")
                   for a in (data.get("answers") or []) if a.get("exercise_id")}

        correct = 0
        total = max(len(exercises), 1)
        for ex in exercises:
            user_ans = (answers.get(ex.id) or "").strip()
            is_correct = user_ans.lower() == (ex.correct_answer or "").strip().lower()
            attempt = ExerciseAttempt.objects.create(
                user=request.user, exercise=ex,
                user_answer=user_ans, is_correct=is_correct,
                score=1.0 if is_correct else 0.0,
            )
            try:
                process_attempt(request.user, ex, attempt)
            except Exception:
                pass
            if is_correct:
                correct += 1
        complete(assessment, score=correct * 100.0 / total)

        # Best-effort: refresh XP/streak/achievements right after the exam.
        try:
            from motivation.services.motivation_engine import run_for_user
            run_for_user(request.user)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("exam_play: motivation engine failed")

        from django.http import JsonResponse
        return JsonResponse({
            "ok": True,
            "score": round(assessment.score, 1),
            "correct": correct,
            "total": total,
            "redirect": f"/dashboard/exam/{assessment.id}/result/",
        })

    if assessment.status == "pending":
        assessment.status = "in_progress"
        if not assessment.started_at:
            assessment.started_at = timezone.now()
        assessment.save(update_fields=["status", "started_at"])

    # Serialise the exercises to a JSON-safe dict for the player JS.
    import json
    exercises_payload = json.dumps([
        {
            "id": ex.id,
            "question_type": ex.question_type,
            "question": ex.question,
            "options": list(ex.options or []),
            "correct_answer": ex.correct_answer,
            "explanation": ex.explanation or "",
            "skill": ex.skill.name if ex.skill_id else "",
            "topic": ex.topic.name if ex.topic_id else "",
            "metadata": ex.metadata or {},
        }
        for ex in exercises
    ])

    return render(request, "lessons/exam_play.html", {
        "assessment": assessment,
        "exercises_json": exercises_payload,
        "exercises_count": len(exercises),
    })


@login_required
@require_http_methods(["GET"])
def exam_result(request, assessment_id):
    from learning_core.models import WeeklyAssessment
    assessment = get_object_or_404(
        WeeklyAssessment, pk=assessment_id, user=request.user
    )
    return render(request, "lessons/exam_result.html", {
        "assessment": assessment,
    })


@login_required
@require_http_methods(["GET", "POST"])
def weekly_assessment(request, assessment_id):
    """Legacy weekly-assessment endpoint — redirects to the new player so
    every assessment shares one Duolingo-style UX."""
    return redirect("exam_play", assessment_id=assessment_id)


@login_required
@require_http_methods(["GET", "POST"])
def weekly_assessment_legacy(request, assessment_id):
    """Server-rendered fallback (kept available; no link points at it)."""
    from learning_core.models import (
        AdaptiveExercise,
        ExerciseAttempt,
        WeeklyAssessment,
    )
    from learning_core.services.adaptive_difficulty import process_attempt
    from learning_core.services.weekly_assessment import complete

    assessment = get_object_or_404(
        WeeklyAssessment, pk=assessment_id, user=request.user
    )
    exercises = list(assessment.exercises.all())

    if request.method == "POST":
        correct = 0
        total = max(len(exercises), 1)
        for ex in exercises:
            answer = (request.POST.get(f"ex_{ex.id}") or "").strip()
            is_correct = answer.lower() == (ex.correct_answer or "").strip().lower()
            attempt = ExerciseAttempt.objects.create(
                user=request.user,
                exercise=ex,
                user_answer=answer,
                is_correct=is_correct,
                score=1.0 if is_correct else 0.0,
            )
            try:
                process_attempt(request.user, ex, attempt)
            except Exception:
                pass
            if is_correct:
                correct += 1
        complete(assessment, score=correct * 100.0 / total)
        return render(request, "lessons/weekly_assessment_result.html", {
            "assessment": assessment,
            "score": assessment.score,
            "correct": correct,
            "total": total,
        })

    if assessment.status == "pending":
        assessment.status = "in_progress"
        if not assessment.started_at:
            assessment.started_at = timezone.now()
        assessment.save(update_fields=["status", "started_at"])

    return render(request, "lessons/weekly_assessment.html", {
        "assessment": assessment,
        "exercises": exercises,
    })
