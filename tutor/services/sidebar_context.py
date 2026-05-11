"""Build the AI Tutor right-rail learning sidebar payload.

Pure read service. Returns primitives only (strings, ints, lists of dicts)
so the template can render without touching ORM relations and so the
payload is cheap to JSON-serialise if we later expose it over an endpoint.

Composition mirrors what the prompt context builder collects, plus the
motivation totals (XP / streak) and pending recommendations. Everything
is best-effort: a missing model or empty queryset degrades to an empty
list, never an exception, because the sidebar is decorative — the chat
must still load if any source is unavailable.
"""
from __future__ import annotations

from typing import Optional

MAX_WEAKNESSES = 3
MAX_RECENT_MISTAKES = 3
MAX_RECOMMENDATIONS = 3


def _safe(call, default):
    try:
        return call()
    except Exception:
        return default


def _level(user) -> str:
    from learning_core.models import StudentLearningProfile

    profile = StudentLearningProfile.objects.filter(user=user).first()
    if profile and profile.current_cefr_level:
        return profile.current_cefr_level
    return getattr(getattr(user, "profile", None), "cefr_level", "") or "B1"


def _weaknesses(user) -> list[dict]:
    from learning_core.services.weakness_engine import get_top_weaknesses

    out = []
    for w in get_top_weaknesses(user, limit=MAX_WEAKNESSES) or []:
        label = (
            (w.grammar_topic.name if w.grammar_topic else None)
            or (w.skill.name if w.skill else None)
            or "general"
        )
        out.append({"label": label, "priority": round(float(w.priority_score or 0), 1)})
    return out


def _recent_mistakes(user) -> list[dict]:
    from learning_core.models import UserError

    qs = (
        UserError.objects.filter(user=user)
        .order_by("-created_at")[:MAX_RECENT_MISTAKES]
    )
    out = []
    for e in qs:
        fragment = (e.original_text or "").strip()[:80]
        if not fragment:
            continue
        out.append({
            "fragment": fragment,
            "type": e.error_type or "",
        })
    return out


def _recommendations(user) -> list[dict]:
    from learning_core.models import LearningRecommendation

    qs = (
        LearningRecommendation.objects
        .filter(user=user, status="pending")
        .order_by("-priority", "-created_at")[:MAX_RECOMMENDATIONS]
    )
    return [{"title": r.title or "", "type": r.recommendation_type or ""} for r in qs]


def _xp_streak(user) -> dict:
    """Pull XP totals and current streak; both are optional decorations."""
    out = {"xp": None, "level_number": None, "streak_days": None}
    try:
        from motivation.models import UserXP, LearnerActivitySnapshot

        xp = UserXP.objects.filter(user=user).first()
        if xp:
            out["xp"] = int(xp.total_xp or 0)
            out["level_number"] = int(xp.level_number or 1)
        snap = (
            LearnerActivitySnapshot.objects
            .filter(user=user)
            .order_by("-date")
            .first()
        )
        if snap:
            out["streak_days"] = int(snap.current_streak_days or 0)
    except Exception:
        pass
    return out


def build_sidebar_payload(user) -> dict:
    """Compose every section the right-rail needs.

    Each subsection is wrapped in `_safe` so a partial outage in one
    learning subsystem (weakness engine, recommendation engine) doesn't
    break the chat page.
    """
    return {
        "level": _safe(lambda: _level(user), "B1"),
        "weaknesses": _safe(lambda: _weaknesses(user), []),
        "recent_mistakes": _safe(lambda: _recent_mistakes(user), []),
        "recommendations": _safe(lambda: _recommendations(user), []),
        "motivation": _safe(lambda: _xp_streak(user),
                            {"xp": None, "level_number": None, "streak_days": None}),
    }
