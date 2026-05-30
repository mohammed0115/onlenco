"""Stateful runner for a single ChallengeSession.

Pure server-side: every transition (start / answer / continue /
complete) is a single function that takes the current state, persists
the next state, and returns the dict the view needs.

The view layer is a thin wrapper — all business rules live here.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone


logger = logging.getLogger(__name__)

from courses.models import (
    ChallengeAnswer, ChallengeSession, CourseLessonProgress, Lesson,
    LessonQuestion, LessonQuiz,
)
from courses.services import (
    challenge_composer, challenge_grading, challenge_rewards,
)


# ----------------------------------------------------------------
# Public API
# ----------------------------------------------------------------

class ChallengeError(Exception):
    """Domain error from the runner. Maps to a clean 4xx upstream."""


@transaction.atomic
def start_or_resume(user, lesson: Lesson) -> ChallengeSession:
    """Return an active session for (user, lesson).

    If one already exists in `started` / `in_progress`, return it as-is
    (true resume — never reset progress). Otherwise compose a fresh
    sequence and create one. Raises `ChallengeError` if the lesson has
    no quiz or no playable questions.
    """
    quiz: Optional[LessonQuiz] = getattr(lesson, "quiz", None)
    if quiz is None or not quiz.is_active:
        raise ChallengeError("Lesson has no active quiz.")

    existing = (
        ChallengeSession.objects
        .filter(user=user, lesson=lesson, status__in=("started", "in_progress"))
        .first()
    )
    if existing is not None:
        return existing

    qids = challenge_composer.compose_question_ids(quiz)
    if not qids:
        raise ChallengeError("No playable questions in this lesson's quiz.")

    return ChallengeSession.objects.create(
        user=user,
        lesson=lesson,
        quiz=quiz,
        status="in_progress",
        question_ids=qids,
        current_question_index=0,
        total_questions=len(qids),
        hearts_total=challenge_rewards.HEARTS_TOTAL,
        hearts_remaining=challenge_rewards.HEARTS_TOTAL,
    )


def get_current_question(session: ChallengeSession) -> Optional[LessonQuestion]:
    """Return the LessonQuestion the session is currently parked on,
    or None if the session has walked past the last card."""
    idx = session.current_question_index
    if idx >= session.total_questions:
        return None
    qid = session.question_ids[idx]
    return LessonQuestion.objects.filter(pk=qid).first()


def has_answered_current(session: ChallengeSession) -> Optional[ChallengeAnswer]:
    """Returns the existing ChallengeAnswer row if the student already
    submitted the current card (refresh-safe). Otherwise None."""
    q = get_current_question(session)
    if q is None:
        return None
    return ChallengeAnswer.objects.filter(session=session, question=q).first()


@transaction.atomic
def submit_answer(
    session: ChallengeSession,
    question: LessonQuestion,
    raw_response: Any,
    *,
    time_spent_seconds: int = 0,
) -> ChallengeAnswer:
    """Grade `raw_response` against `question` and persist the result.

    Guards:
      * Refuses if the session is no longer active.
      * Refuses if `question` is not the session's current card.
      * Idempotent: a second call for the same (session, question)
        returns the existing answer rather than scoring twice.
    """
    if not session.is_active:
        raise ChallengeError("Session is no longer active.")
    current = get_current_question(session)
    if current is None:
        raise ChallengeError("Session has no current question.")
    if current.pk != question.pk:
        raise ChallengeError("That isn't the current question.")

    # Idempotency — if the row already exists, return it.
    existing = ChallengeAnswer.objects.filter(
        session=session, question=question,
    ).first()
    if existing is not None:
        return existing

    grade = challenge_grading.grade(question, raw_response)
    is_correct = bool(grade.get("is_correct"))
    xp = challenge_rewards.xp_for_answer(question=question, is_correct=is_correct)
    heart_lost = challenge_rewards.heart_loss_for_answer(is_correct=is_correct)

    answer = ChallengeAnswer.objects.create(
        session=session,
        question=question,
        user_answer=_coerce_user_answer(raw_response),
        is_correct=is_correct,
        score=float(grade.get("score", 0.0)),
        xp_awarded=xp,
        heart_lost=heart_lost,
        feedback_en=grade.get("feedback_en", ""),
        feedback_ar=grade.get("feedback_ar", ""),
        time_spent_seconds=max(0, int(time_spent_seconds or 0)),
    )

    # Apply session-level deltas.
    if is_correct:
        session.correct_count += 1
        session.xp_earned += xp
        credited = challenge_rewards.credit_answer_xp(
            session.user, amount=xp, answer=answer, session=session,
        )
        # Daily-goal progress tracks the actual XP credited.
        if credited:
            try:
                from motivation.services import daily_goal_service
                daily_goal_service.update_daily_goal_progress(
                    session.user, credited,
                )
            except Exception:
                logger.exception("Daily goal update failed (session=%s)", session.pk)
    else:
        session.wrong_count += 1
        if heart_lost:
            try:
                from motivation.services import hearts_service
                hearts_service.apply_wrong_answer(session)
            except Exception:
                logger.exception("Heart loss failed (session=%s)", session.pk)

    # Phase 6 — mastery + mistake processing. Idempotent via MasteryEvent
    # (one row per ChallengeAnswer). If the answer was a duplicate (re-
    # submit branch above already returned), this never runs.
    try:
        from learning_core.services import mastery_service
        mastery_service.process_challenge_answer(answer)
    except Exception:
        logger.exception("Mastery processing failed (answer=%s)", answer.pk)

    # Session goes into in_progress at first answer.
    if session.status == "started":
        session.status = "in_progress"

    # Failure (heart depletion) ends the session immediately at the
    # current card — the student sees the Summary screen with
    # "Practice Again" instead of a Continue button.
    if session.hearts_remaining == 0:
        session.status = "failed"
        session.completed_at = timezone.now()
        _on_session_terminate(session, perfect=False)

    session.save()
    return answer


@transaction.atomic
def continue_to_next(session: ChallengeSession) -> ChallengeSession:
    """Advance to the next card.

    If the current card hasn't been answered, this is a no-op (refresh
    safety). If we walked past the last card, the session is marked
    completed and we credit the completion bonus.
    """
    if session.status == "failed":
        return session
    if not session.is_active:
        raise ChallengeError("Session is no longer active.")

    answered = ChallengeAnswer.objects.filter(
        session=session,
        question_id=session.question_ids[session.current_question_index],
    ).exists() if session.total_questions else False
    if not answered:
        # Can't advance — current card not yet submitted.
        return session

    session.current_question_index += 1
    if session.current_question_index >= session.total_questions:
        perfect = (session.wrong_count == 0)
        session.status = "completed"
        session.completed_at = timezone.now()
        _on_session_terminate(session, perfect=perfect)
    session.save()
    return session


def abandon(session: ChallengeSession) -> ChallengeSession:
    """Mark a session abandoned (e.g. user navigated away for too long)."""
    if session.is_active:
        session.status = "abandoned"
        session.save(update_fields=["status", "updated_at"])
    return session


# ----------------------------------------------------------------
# Internals
# ----------------------------------------------------------------

def _coerce_user_answer(raw) -> str:
    """Persist whatever the student submitted as a JSON-safe string."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    try:
        import json
        return json.dumps(raw, ensure_ascii=False)
    except Exception:
        return str(raw)


def _on_session_terminate(session: ChallengeSession, *, perfect: bool) -> None:
    """End-of-session bookkeeping: completion + perfect bonuses (ledger-
    safe), CourseLessonProgress mirror, streak record + badge evaluation.

    Idempotent — re-entering this function for the SAME session ID is
    safe because every grant is keyed by the XP ledger on
    (source_type, source_id=session.pk).
    """
    if session.status == "completed":
        # Persist completion now so any downstream reader that counts
        # `ChallengeSession.objects.filter(status="completed")` (the badge
        # evaluator does this) sees the current row.
        if session.completed_at is None:
            session.completed_at = timezone.now()
        session.save(update_fields=["status", "completed_at", "updated_at"])

        completion = challenge_rewards.credit_completion_bonus(
            session.user, session=session,
        )
        perfect_bonus = challenge_rewards.credit_perfect_bonus(
            session.user, session=session,
        )
        session.xp_earned += (completion + perfect_bonus)

        # Daily-goal progress from the completion/perfect bonuses.
        if (completion + perfect_bonus) > 0:
            try:
                from motivation.services import daily_goal_service
                daily_goal_service.update_daily_goal_progress(
                    session.user, completion + perfect_bonus,
                    challenges_delta=1,
                )
            except Exception:
                logger.exception("Daily-goal completion update failed (session=%s)", session.pk)

        # Streak source-of-truth.
        try:
            from motivation.services import streak_v2
            streak_v2.record_learning_activity(
                session.user, "challenge_completed",
                xp_earned=completion + perfect_bonus,
                metadata={"challenge_session": session.pk,
                          "perfect": bool(perfect)},
            )
        except Exception:
            logger.exception("Streak record failed (session=%s)", session.pk)

        # Badge evaluation.
        try:
            from motivation.services import badge_catalog
            badge_catalog.evaluate_badges_after_challenge(session.user, session)
        except Exception:
            logger.exception("Badge evaluation failed (session=%s)", session.pk)

    # Mirror the score onto CourseLessonProgress so the existing
    # dashboard / pass-fail logic picks it up. We do NOT mark
    # video_completed — that belongs to the lesson page flow.
    score_pct = session.accuracy_pct
    progress, _ = CourseLessonProgress.objects.get_or_create(
        user=session.user, lesson=session.lesson,
    )
    passing = int(getattr(session.quiz, "passing_score", 70) or 70)
    if progress.quiz_score is None or score_pct > progress.quiz_score:
        progress.quiz_score = score_pct
        progress.quiz_passed = score_pct >= passing
        if progress.is_complete and not progress.completed_at:
            progress.completed_at = timezone.now()
        progress.save()
