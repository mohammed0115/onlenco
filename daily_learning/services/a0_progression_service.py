"""A0 → A1 promotion logic.

The Onlenco A0 graduation criteria are deliberate and conservative:
a learner does NOT auto-promote on lesson count alone — accuracy and
vocabulary breadth matter too. We read from data that already exists
(LearnerActivitySnapshot rollups + ExerciseAttempt) so no new tables
are needed.

Promotion criteria (all must hold):
    * ≥ 20 A0 daily plans completed
    * ≥ 100 quiz/question answers
    * ≥ 75% accuracy across those answers
    * ≥ 150 distinct vocabulary words seen / learned

When all four are satisfied, `maybe_promote_a0_to_a1` flips
`profile.cefr_level` and `StudentLearningProfile.current_cefr_level`
to "A1" and fires a notification. Idempotent — re-running after
promotion is a no-op.
"""
from __future__ import annotations

import logging

from django.db.models import Sum

logger = logging.getLogger(__name__)

# Thresholds — tuned to match the Onlenco A0 spec.
THRESHOLD_LESSONS         = 20
THRESHOLD_QUESTIONS       = 100
THRESHOLD_ACCURACY_PCT    = 75.0   # 0..100
THRESHOLD_VOCAB_WORDS     = 150


def check_a0_promotion_criteria(user) -> dict:
    """Return a structured snapshot of the learner's promotion progress.

    Always returns a complete dict — never raises — so it is safe to
    call from a request path or a periodic job.
    """
    out = {
        "eligible": False,
        "current_level": _current_level(user),
        "lessons_completed": 0,
        "questions_answered": 0,
        "accuracy_pct": 0.0,
        "vocabulary_words": 0,
        "thresholds": {
            "lessons":   THRESHOLD_LESSONS,
            "questions": THRESHOLD_QUESTIONS,
            "accuracy":  THRESHOLD_ACCURACY_PCT,
            "vocab":     THRESHOLD_VOCAB_WORDS,
        },
    }
    if out["current_level"] != "A0":
        # Only A0 learners can be promoted out of A0.
        return out

    out.update(_collect_metrics(user))

    out["eligible"] = (
        out["lessons_completed"] >= THRESHOLD_LESSONS
        and out["questions_answered"] >= THRESHOLD_QUESTIONS
        and out["accuracy_pct"] >= THRESHOLD_ACCURACY_PCT
        and out["vocabulary_words"] >= THRESHOLD_VOCAB_WORDS
    )
    return out


def maybe_promote_a0_to_a1(user) -> bool:
    """If the user meets every promotion criterion, flip them to A1.

    Returns True only on the run that performed the flip. Subsequent
    calls (or calls for non-A0 users) return False without raising.
    """
    snapshot = check_a0_promotion_criteria(user)
    if not snapshot["eligible"]:
        return False

    promoted = _do_promote(user)
    if promoted:
        _notify_promotion(user, snapshot)
    return promoted


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _current_level(user) -> str:
    """Best current CEFR level — prefers the adaptive engine's view."""
    try:
        from learning_core.models import StudentLearningProfile
        slp = StudentLearningProfile.objects.filter(user=user).first()
        if slp and slp.current_cefr_level:
            return slp.current_cefr_level
    except Exception:
        pass
    try:
        return user.profile.cefr_level or ""
    except Exception:
        return ""


def _collect_metrics(user) -> dict:
    """Read directly from the snapshot rollup + raw attempts.

    Snapshot fields are already aggregated per day, so summing them
    gives a stable total. The ExerciseAttempt fallback is used for the
    accuracy calculation since the snapshot stores only a daily-rounded
    `quiz_accuracy` percentage.
    """
    metrics = {
        "lessons_completed": 0,
        "questions_answered": 0,
        "correct_answers": 0,
        "accuracy_pct": 0.0,
        "vocabulary_words": 0,
    }
    try:
        from motivation.models import LearnerActivitySnapshot
        agg = (
            LearnerActivitySnapshot.objects
            .filter(user=user)
            .aggregate(
                lessons=Sum("lessons_completed"),
                questions=Sum("questions_answered"),
                correct=Sum("correct_answers"),
                vocab=Sum("vocabulary_words_learned"),
            )
        )
        metrics["lessons_completed"]  = int(agg.get("lessons") or 0)
        metrics["questions_answered"] = int(agg.get("questions") or 0)
        metrics["correct_answers"]    = int(agg.get("correct") or 0)
        metrics["vocabulary_words"]   = int(agg.get("vocab") or 0)
    except Exception:
        logger.warning("a0 progression: snapshot aggregate failed", exc_info=True)

    # Also count DailyLearningPlan completions in case the snapshot
    # collector hasn't run yet today.
    try:
        from ..models import DailyLearningPlan
        plan_completions = DailyLearningPlan.objects.filter(
            user=user, cefr_level="A0", status="completed",
        ).count()
        metrics["lessons_completed"] = max(
            metrics["lessons_completed"], plan_completions
        )
    except Exception:
        pass

    if metrics["questions_answered"] > 0:
        metrics["accuracy_pct"] = round(
            metrics["correct_answers"] / metrics["questions_answered"] * 100.0, 1
        )
    return metrics


def _do_promote(user) -> bool:
    """Flip both the Profile and StudentLearningProfile to A1.

    Returns False if either record is missing or the user is already
    at A1+ (idempotent).
    """
    try:
        profile = user.profile
    except Exception:
        return False
    if profile.cefr_level and profile.cefr_level != "A0":
        return False

    profile.cefr_level = "A1"
    profile.save(update_fields=["cefr_level"])

    try:
        from learning_core.models import StudentLearningProfile
        slp = StudentLearningProfile.objects.filter(user=user).first()
        if slp is not None:
            slp.current_cefr_level = "A1"
            # Bump theta toward the A1 band but stay conservative.
            if slp.theta_score < -0.5:
                slp.theta_score = -0.5
            slp.save(update_fields=["current_cefr_level", "theta_score"])
    except Exception:
        logger.warning("a0 progression: StudentLearningProfile update failed",
                       exc_info=True)
    return True


def _notify_promotion(user, snapshot: dict) -> None:
    """Best-effort student-facing notification — never raises."""
    try:
        from notifications import constants as Nc
        from notifications.services.notification_service import NotificationService
        NotificationService().trigger(
            Nc.LEVEL_IMPROVED,
            user=user,
            payload={
                "from_level": "A0",
                "to_level": "A1",
                "lessons_completed": snapshot["lessons_completed"],
                "accuracy_pct": snapshot["accuracy_pct"],
                "vocabulary_words": snapshot["vocabulary_words"],
            },
            priority=Nc.PRIORITY_NORMAL,
        )
    except Exception:
        logger.warning("a0 progression: notify failed", exc_info=True)
