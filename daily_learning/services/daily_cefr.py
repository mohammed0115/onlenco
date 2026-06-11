"""CEFR helpers for the Daily Quiz (Prompt 18.3C).

Single, explicit source of truth for "which level is this learner's daily plan
tuned to", plus guards so a plan never serves a level ABOVE the learner (A0
must never see A1+). ``Profile.cefr_level`` is authoritative — it is set
deliberately by onboarding (Beginner → A0), placement result, and the A0→A1
promotion service. ``learning_core`` theta can drift, so it is only a fallback.
"""
from __future__ import annotations

# Ascending CEFR order used for "same-or-lower" comparisons.
LEVEL_ORDER = ("A0", "A1", "A2", "B1", "B2", "C1", "C2", "C3")
_DEFAULT = "A1"


def _band(level) -> str:
    return (str(level or "")[:2]).upper()


def resolve_daily_cefr_level(user) -> str:
    """The CEFR level the learner's daily plan should target.

    Order: Profile.cefr_level → learning_core current_cefr_level → "A1".
    """
    profile = getattr(user, "profile", None)
    lvl = getattr(profile, "cefr_level", None)
    if lvl:
        return lvl
    try:
        from learning_core.models import StudentLearningProfile
        lp = StudentLearningProfile.objects.filter(user=user).first()
        if lp and getattr(lp, "current_cefr_level", ""):
            return lp.current_cefr_level
    except Exception:
        pass
    return _DEFAULT


def allowed_daily_levels(level) -> list[str]:
    """Levels a learner at ``level`` may be served: same level or LOWER.

    Daily content never escalates above the learner's official level; when the
    bank is short we may fall back to easier (lower) items, never harder ones.
    """
    band = _band(level)
    if band not in LEVEL_ORDER:
        return [_DEFAULT]
    idx = LEVEL_ORDER.index(band)
    return list(LEVEL_ORDER[: idx + 1])


def is_level_allowed(item_level, student_level) -> bool:
    """True when an item at ``item_level`` is OK for ``student_level``
    (same or lower). Unknown item levels are treated as allowed (no level)."""
    ib = _band(item_level)
    if ib not in LEVEL_ORDER:
        return True
    return ib in allowed_daily_levels(student_level)
