"""Smart review queue — prioritise the mistakes to surface first.

Sort order (stable):
  1. Most-overdue first (smallest next_review_at)
  2. High severity before low
  3. Lower mastery_score on the linked skill first
  4. Higher review_count first (the "stuck" ones)

This module never mutates state — pure read-side. The Challenge
engine still owns the writes.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.db.models import F, Value, IntegerField, Case, When
from django.utils import timezone


SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def build_review_queue(user, *, limit: int = 20, now=None) -> list[dict]:
    """Return ordered dicts ready to render or hand to a UI.

    Each dict shape:
        {
          mistake: StudentMistake,
          skill: Skill or None,
          question: LessonQuestion,
          due_in_minutes: int (negative when overdue),
          severity: str,
          mastery_score: float or None,
        }
    """
    from ..models import SkillMastery, StudentMistake
    now = now or timezone.now()
    upper = now + timedelta(hours=24)
    mistakes = (
        StudentMistake.objects
        .filter(user=user, mastered=False, next_review_at__lte=upper)
        .select_related("skill", "question", "lesson")
    )
    # Bulk-load masteries to avoid N+1.
    skill_ids = {m.skill_id for m in mistakes if m.skill_id}
    mastery_by_skill = {
        m.skill_id: m.mastery_score
        for m in SkillMastery.objects.filter(
            user=user, skill_id__in=skill_ids,
        )
    }

    def _key(m):
        due_at = m.next_review_at or now
        return (
            due_at,
            SEVERITY_RANK.get(m.severity, 1),
            mastery_by_skill.get(m.skill_id, 100.0),
            -int(m.review_count or 0),
        )

    ordered = sorted(mistakes, key=_key)[:limit]
    out = []
    for m in ordered:
        due_at = m.next_review_at or now
        delta = (due_at - now).total_seconds() / 60.0
        out.append({
            "mistake":         m,
            "skill":           m.skill,
            "question":        m.question,
            "due_in_minutes":  int(delta),
            "severity":        m.severity,
            "mastery_score":   mastery_by_skill.get(m.skill_id),
        })
    return out


def count_due_now(user, *, now=None) -> int:
    from ..models import StudentMistake
    now = now or timezone.now()
    return StudentMistake.objects.filter(
        user=user, mastered=False, next_review_at__lte=now,
    ).count()
