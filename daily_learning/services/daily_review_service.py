"""Build review-mistake items from the user's recent errors.

We pull from `learning_core.UserError` (raw errors from quizzes, tutor,
writing, etc.) and from active `UserWeakness` rows to choose at most
N "review" slots for today's plan.

The review item shows the student their wrong answer, the corrected
version, and asks them to re-attempt — but the re-attempt is captured
as a fresh quiz question, so we can mark the underlying weakness as
"improving" if they get it right.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_recent_mistakes(user, *, limit: int = 3, days: int | None = None) -> list[dict]:
    """Return up to `limit` recent UserError rows as plain dicts.

    Returns empty list when the learning_core app isn't installed or
    the user has no recent errors.
    """
    try:
        from learning_core.models import UserError
    except Exception:
        return []

    lookback_days = days if days is not None else getattr(
        settings, "DAILY_LEARNING_MISTAKE_LOOKBACK_DAYS", 7
    )
    since = timezone.now() - timedelta(days=lookback_days)
    qs = (UserError.objects
          .filter(user=user, created_at__gte=since)
          .exclude(corrected_text="")
          .order_by("-severity", "-created_at")[: limit * 2])  # over-fetch
    seen_signatures: set[str] = set()
    picks: list[dict] = []
    for err in qs:
        sig = (err.original_text or "").strip().lower()
        if not sig or sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        picks.append({
            "error_id": err.id,
            "original_text": err.original_text,
            "corrected_text": err.corrected_text,
            "error_type": err.error_type,
            "explanation": err.explanation,
            "severity": err.severity,
            "skill_id": err.skill_id,
            "grammar_topic_id": err.grammar_topic_id,
        })
        if len(picks) >= limit:
            break
    return picks


def get_top_weaknesses(user, *, limit: int = 2) -> list[dict]:
    """Return top active weaknesses as plain dicts, ordered by priority."""
    try:
        from learning_core.models import UserWeakness
    except Exception:
        return []
    qs = (UserWeakness.objects
          .filter(user=user, status="active")
          .select_related("skill", "grammar_topic")
          .order_by("-priority_score")[:limit])
    out = []
    for w in qs:
        out.append({
            "weakness_id": w.id,
            "skill_name": w.skill.name if w.skill_id else None,
            "skill_category": w.skill.category if w.skill_id else None,
            "grammar_topic_name": w.grammar_topic.name if w.grammar_topic_id else None,
            "grammar_topic_slug": w.grammar_topic.slug if w.grammar_topic_id else None,
            "priority": w.priority_score,
        })
    return out


def build_review_items(user, *, limit: int = 2, language: str = "en") -> list[dict]:
    """Build review_mistake item dicts ready for DailyLearningItem creation."""
    mistakes = get_recent_mistakes(user, limit=limit)
    items: list[dict] = []
    for m in mistakes:
        original = (m["original_text"] or "").strip()
        corrected = (m["corrected_text"] or "").strip()
        if not corrected or corrected == original:
            continue
        if language == "ar":
            title = "راجع خطأً سابقاً"
            instructions = "اقرأ ما كتبته، ثم اقرأ التصحيح. حاول كتابة الجملة الصحيحة بنفسك."
        else:
            title = "Review a past mistake"
            instructions = "Read what you wrote, then read the correction. Try writing the correct version yourself."
        items.append({
            "item_type": "review_mistake",
            "title": title,
            "instructions": instructions,
            "content_text": f"You wrote: {original}\nCorrection: {corrected}",
            "question": f"Try again: rewrite the sentence correctly.",
            "options": [],
            "correct_answer": corrected,
            "explanation": m["explanation"] or "",
            "skill": (m.get("skill_category") or "mixed"),
            "difficulty_score": 0.3,
            "estimated_minutes": 2,
            "metadata": {
                "source": "user_error",
                "user_error_id": m["error_id"],
                "weakness_id": None,
            },
        })
    return items
