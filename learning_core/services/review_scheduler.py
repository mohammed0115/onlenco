"""Spaced review scheduling — Phase 6.

Rules (intentionally simple, no SM-2 yet):

  On a fresh mistake (review_count == 0):
      next_review_at = now + 24h
  On 2nd attempt still-wrong (review_count == 1):
      next_review_at = now + 12h
  On 3rd+ wrong attempt (review_count >= 2):
      next_review_at = now + 4h

  When the user answers correctly AFTER a mistake exists:
      if mastery_score >= 90 → mastered=True, next_review_at = now + 7 days
      elif mastery_score >= 70 → next_review_at = now + 3 days
      else → leave next_review_at alone (still due)

The `mastery_score` argument is the score the OWNING SkillMastery row
holds AFTER the answer has been applied — callers pass it in.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable, Optional

from django.utils import timezone


def schedule_mistake_review(mistake) -> None:
    """Set `next_review_at` based on the current `review_count`."""
    now = timezone.now()
    if mistake.review_count <= 0:
        delta = timedelta(days=1)
    elif mistake.review_count == 1:
        delta = timedelta(hours=12)
    else:
        delta = timedelta(hours=4)
    mistake.next_review_at = now + delta


def mark_mistake_improved(
    mistake, *, mastery_score: float,
) -> None:
    """Move the next_review_at out (or mark mastered) on a correct
    follow-up. NEVER mutates `review_count`."""
    now = timezone.now()
    if mastery_score >= 90:
        mistake.mastered = True
        mistake.next_review_at = now + timedelta(days=7)
    elif mastery_score >= 70:
        mistake.next_review_at = now + timedelta(days=3)
    # Else: still weak; keep next_review_at where it is.


def get_due_mistakes(user, *, limit: int = 10, now=None) -> list:
    """Return mistakes whose next_review_at has passed AND not yet
    mastered, sorted by oldest-due first."""
    from ..models import StudentMistake
    now = now or timezone.now()
    return list(
        StudentMistake.objects
        .filter(user=user, mastered=False, next_review_at__lte=now)
        .select_related("skill", "question")
        .order_by("next_review_at")[:limit]
    )


def get_review_queue(user, *, limit: int = 25, now=None) -> list:
    """Like `get_due_mistakes` but includes upcoming (next 24h) too —
    useful for a "what's coming" preview on the dashboard."""
    from ..models import StudentMistake
    now = now or timezone.now()
    upper = now + timedelta(hours=24)
    return list(
        StudentMistake.objects
        .filter(user=user, mastered=False, next_review_at__lte=upper)
        .select_related("skill", "question")
        .order_by("next_review_at")[:limit]
    )
