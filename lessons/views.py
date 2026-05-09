from urllib.parse import parse_qs, urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

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
    """Student dashboard. Shows the placement-test prompt (if not yet
    taken), the lesson grid, and a subscribe CTA when the student isn't
    on an active plan."""

    profile = request.user.profile
    qs = Lesson.objects.all()

    # If the learner has a CEFR level, surface their level + the next two
    # levels so they can see the path forward without overwhelming them.
    if profile.cefr_level:
        order = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]
        try:
            i = order.index(profile.cefr_level)
            visible = order[i:i + 3]
            qs = qs.filter(level__in=visible)
        except ValueError:
            pass

    lessons = list(qs)
    progress_map = {
        p.lesson_id: p
        for p in LessonProgress.objects.filter(user=request.user, lesson__in=lessons)
    }
    for l in lessons:
        l.progress = progress_map.get(l.id)

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
        # Hero card for beginners with no progress yet — set below.
        "beginner_first_lesson": None,
    }

    # Day-1 hero for beginner-path users: surface the first lesson as a
    # full-bleed card so the dashboard isn't a wall of empty grids. Skip
    # for placement-test users (they get the recommendations engine).
    if (
        getattr(profile, "onboarding_path", "") == "beginner_start"
        and not LessonProgress.objects.filter(user=request.user).exists()
    ):
        try:
            from accounts.onboarding import first_beginner_lesson
            learning_summary["beginner_first_lesson"] = first_beginner_lesson()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("beginner first-lesson lookup failed")

    try:
        from learning_core.models import (
            ExerciseAttempt,
            LearningRecommendation,
            UserError,
        )
        from learning_core.services.weakness_engine import get_top_weaknesses

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

    return render(request, "lessons/dashboard.html", {
        "profile": profile,
        "lessons": lessons,
        "is_subscribed": profile.is_subscribed,
        "next_club_event": next_club_event,
        "next_club_rsvp": next_club_rsvp,
        "last_rejected": last_rejected,
        "learning_summary": learning_summary,
        "motivation": motivation_widget,
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
                widget["cefr_progress"] = cefr_progress(prof.theta_score or 0.0)
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
def mark_video_complete(request, pk):
    if not request.user.profile.is_subscribed:
        return HttpResponseForbidden("Subscription required")

    lesson = get_object_or_404(Lesson, pk=pk)
    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

    if not progress.video_completed:
        progress.video_completed = True
        if progress.is_complete and not progress.completed_at:
            progress.completed_at = timezone.now()
        progress.save()
        messages.success(request, "Marked as watched.")

    return redirect("lesson_detail", pk=lesson.pk)


@login_required
@require_http_methods(["GET", "POST"])
def quiz_attempt(request, pk):
    if not request.user.profile.is_subscribed:
        return HttpResponseForbidden("Subscription required")

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
    try:
        from .services.adaptive_quiz_adapter import process_quiz_submission
        summary = process_quiz_submission(request.user, lesson, results)
        weekly_assessment_id = summary.get("weekly_assessment_triggered")
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
    })


@login_required
@require_http_methods(["GET"])
def daily_exam(request):
    """Start (or resume) today's daily check-in and redirect to the player."""
    from learning_core.services.weekly_assessment import start_daily_assessment

    assessment = start_daily_assessment(request.user)
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
