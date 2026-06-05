"""Placement-speaking policy (Prompt 16.6F) — ONE lifetime attempt, and
fully SEPARATE from the AI-Tutor minute allowance.

The placement speaking test (Part 2) is onboarding: a brand-new student
takes it before any subscription / trial minutes exist. So it must never
touch ``UserDailyQuota`` / ``FreeTrialUsage`` (the AI-Tutor allowance), and
must never be blocked because those minutes are exhausted.

But it is also a one-shot assessment, not free unlimited tutoring: each
student gets exactly ONE *valid* attempt. An attempt only "counts" once the
student has answered at least one question — a connection that dropped
before any answer is ``failed_start`` and is retryable. A re-attempt after a
valid one is only possible via an audited admin reset.

The lifetime gate lives on ``PlacementSpeakingAttempt``; this module is the
single place that reads/writes that policy.
"""
from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from placement.models import PlacementSpeakingAttempt


# --- settings accessors -------------------------------------------------
def is_enabled() -> bool:
    return bool(getattr(settings, "PLACEMENT_SPEAKING_ENABLED", True))


def one_attempt_only() -> bool:
    return bool(getattr(settings, "PLACEMENT_SPEAKING_ONE_ATTEMPT_ONLY", True))


def allow_admin_reset() -> bool:
    return bool(getattr(settings, "PLACEMENT_SPEAKING_ALLOW_ADMIN_RESET", True))


def max_minutes_per_attempt() -> int:
    return int(getattr(settings, "PLACEMENT_SPEAKING_MAX_MINUTES_PER_ATTEMPT", 7))


def max_session_seconds() -> int:
    """Hard per-attempt length cap, in seconds."""
    return max(30, max_minutes_per_attempt() * 60)


# --- the lifetime gate --------------------------------------------------
def blocking_attempt(user):
    """Return the used-attempt row that currently blocks ``user`` (or None).

    A row blocks when it consumed the attempt (``is_used_attempt=True``)
    and has NOT been cleared by an admin reset (``reset_at`` is null).
    """
    return (
        PlacementSpeakingAttempt.objects
        .filter(student=user, is_used_attempt=True, reset_at__isnull=True)
        .order_by("-started_at")
        .first()
    )


def has_used_attempt(user) -> bool:
    return blocking_attempt(user) is not None


def _msg(ar: str, en: str) -> dict:
    return {"ar": ar, "en": en}


# The friendly, support-oriented block message (no technical detail).
BLOCKED_MESSAGE = _msg(
    "لقد أكملت اختبار التحدث لتحديد المستوى من قبل. إذا كنت تعتقد أن هناك مشكلة، "
    "تواصل مع الإدارة لإعادة فتح الاختبار.",
    "You've already completed the speaking placement test. If you think there's "
    "a problem, contact support to reopen the test.",
)
DISABLED_MESSAGE = _msg(
    "اختبار التحديد الصوتي متوقف مؤقتًا. يمكنك إكمال القسم الكتابي الآن والمحاولة لاحقًا.",
    "The speaking placement test is temporarily unavailable. You can finish the "
    "written part now and try again later.",
)


def check_can_start(user) -> tuple[bool, str, dict | None]:
    """Decide whether ``user`` may start a placement speaking call now.

    Returns ``(allowed, code, message)`` where ``message`` is a bilingual
    dict (``None`` when allowed) and ``code`` is a stable machine string.
    """
    if not is_enabled():
        return False, "placement_disabled", DISABLED_MESSAGE
    if one_attempt_only() and has_used_attempt(user):
        return False, "placement_already_used", BLOCKED_MESSAGE
    return True, "ok", None


# --- attempt lifecycle --------------------------------------------------
def open_attempt(user, *, conversation, placement_attempt=None) -> PlacementSpeakingAttempt:
    """Open (or reuse) the in-progress speaking attempt row for this call."""
    row = (
        PlacementSpeakingAttempt.objects
        .filter(student=user, conversation=conversation,
                status=PlacementSpeakingAttempt.STATUS_STARTED,
                completed_at__isnull=True)
        .order_by("-started_at")
        .first()
    )
    if row is not None:
        return row
    return PlacementSpeakingAttempt.objects.create(
        student=user, conversation=conversation,
        placement_attempt=placement_attempt,
        status=PlacementSpeakingAttempt.STATUS_STARTED,
    )


def finalise_attempt(
    row: PlacementSpeakingAttempt, *, seconds: int, question_count: int,
    killed_by_quota: bool = False,
) -> tuple[PlacementSpeakingAttempt, str]:
    """Finalise an attempt from the call outcome. Returns (row, ended_reason).

    With the strict completion gate, an attempt only "counts" (and so only
    consumes the one lifetime attempt) when the student actually COMPLETES
    the speaking section — i.e. answered at least ``PLACEMENT_SPEAKING_MIN_
    ANSWERS`` questions. Anything short of that is retryable:
      * 0 answers          → ``failed_start`` → NOT used (retry).
      * 1..(min-1) answers → ``needs_retry``  → NOT used (retry).
      * >= min answers     → ``completed``    → USED.
    """
    from django.conf import settings as _dj
    M = PlacementSpeakingAttempt
    seconds = max(0, int(seconds or 0))
    question_count = max(0, int(question_count or 0))
    min_answers = int(getattr(_dj, "PLACEMENT_SPEAKING_MIN_ANSWERS", 3))

    if question_count <= 0:
        status, used, ended_reason = M.STATUS_FAILED_START, False, "failed_start"
    elif question_count < min_answers:
        status, used, ended_reason = M.STATUS_NEEDS_RETRY, False, "needs_retry"
    else:
        status, used, ended_reason = M.STATUS_COMPLETED, True, "completed"

    if killed_by_quota and used:
        ended_reason = "killed_by_quota"

    row.status = status
    row.is_used_attempt = used
    row.duration_seconds = seconds
    row.question_count_answered = question_count
    row.completed_at = timezone.now()
    md = dict(row.metadata or {})
    md.update({"ended_reason": ended_reason, "is_used_attempt": used})
    row.metadata = md
    row.save(update_fields=[
        "status", "is_used_attempt", "duration_seconds",
        "question_count_answered", "completed_at", "metadata",
    ])
    return row, ended_reason


def mark_needs_retry(attempt, conversation, answered: int) -> PlacementSpeakingAttempt:
    """Mark the speaking attempt as retryable (NOT used) — for the strict gate.

    ``answered == 0`` → ``failed_start``; otherwise ``needs_retry``. Either
    way ``is_used_attempt=False`` so the student keeps their lifetime attempt
    and can try again without an admin reset.
    """
    M = PlacementSpeakingAttempt
    row = (
        M.objects.filter(student=attempt.user, conversation=conversation)
        .order_by("-started_at").first()
        or M.objects.create(student=attempt.user, conversation=conversation,
                            placement_attempt=attempt)
    )
    row.status = M.STATUS_FAILED_START if int(answered or 0) <= 0 else M.STATUS_NEEDS_RETRY
    row.is_used_attempt = False
    row.question_count_answered = int(answered or 0)
    row.completed_at = timezone.now()
    md = dict(row.metadata or {})
    md.update({"ended_reason": row.status, "is_used_attempt": False})
    row.metadata = md
    row.save()
    return row


def _mark(attempt, conversation, *, status, used, answered):
    M = PlacementSpeakingAttempt
    row = (
        M.objects.filter(student=attempt.user, conversation=conversation)
        .order_by("-started_at").first()
        or M.objects.create(student=attempt.user, conversation=conversation,
                            placement_attempt=attempt)
    )
    row.status = status
    row.is_used_attempt = used
    row.question_count_answered = int(answered or 0)
    row.completed_at = timezone.now()
    md = dict(row.metadata or {})
    md.update({"ended_reason": status, "is_used_attempt": used})
    row.metadata = md
    row.save()
    return row


def mark_failed_system(attempt, conversation, answered: int = 0) -> PlacementSpeakingAttempt:
    """Technical failure (STT/provider) — NOT used, retryable."""
    return _mark(attempt, conversation,
                 status=PlacementSpeakingAttempt.STATUS_FAILED_SYSTEM,
                 used=False, answered=answered)


def mark_unable(attempt, conversation, answered: int) -> PlacementSpeakingAttempt:
    """Student couldn't answer after retries — counts as a USED attempt
    (they had their chance) and finalises conservatively."""
    return _mark(attempt, conversation,
                 status=PlacementSpeakingAttempt.STATUS_UNABLE,
                 used=True, answered=answered)


def result_route(row: PlacementSpeakingAttempt) -> str:
    """Where the browser should go after the call, given the outcome.

    ``completed`` → the result page; a partial/failed attempt → ``retry``
    so the student is never stuck on the call screen. The placement
    finalise view interprets this together with the scored data.
    """
    if row.status == PlacementSpeakingAttempt.STATUS_COMPLETED:
        return "result"
    if row.status == PlacementSpeakingAttempt.STATUS_FAILED_START:
        return "retry"
    return "retry"


class ResetError(Exception):
    """Raised when an admin reset is rejected (disabled / missing reason)."""


def reset_for(student, *, actor, reason: str) -> PlacementSpeakingAttempt | None:
    """Audited admin reset — reopen the speaking test for ``student``.

    Stamps ``reset_by`` / ``reset_at`` / ``reset_reason`` on the blocking
    used attempt (nothing is deleted), which clears it from the blocking
    set so the student may attempt once more. Returns the cleared row, or
    ``None`` if there was nothing to reset.
    """
    if not allow_admin_reset():
        raise ResetError("Admin reset for placement speaking is disabled.")
    reason = (reason or "").strip()
    if not reason:
        raise ResetError("A reset reason is required.")
    row = blocking_attempt(student)
    if row is None:
        return None
    row.reset_by = actor
    row.reset_at = timezone.now()
    row.reset_reason = reason[:2000]
    md = dict(row.metadata or {})
    md["admin_reset"] = True
    row.metadata = md
    row.save(update_fields=["reset_by", "reset_at", "reset_reason", "metadata"])
    return row
