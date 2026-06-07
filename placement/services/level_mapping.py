"""Configurable written-percentage → CEFR level mapping (Placement Phase 5).

The mapping lives in ``settings.PLACEMENT_LEVEL_MAP`` so it can be retuned
without code/template changes. It is used as the level signal for the
written section and as the fallback final level when no richer signal
(e.g. a speaking-call CEFR estimate) is available.
"""
from __future__ import annotations

from django.conf import settings

DEFAULT_BANDS = [
    (20, "A0"), (40, "A1"), (60, "A2"), (75, "B1"),
    (88, "B2"), (95, "C1"), (100, "C2"),
]

LEVEL_ORDER = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]


def cap_level(level: str, ceiling: str) -> str:
    """Return ``level`` lowered to ``ceiling`` if it sits above it."""
    try:
        li = LEVEL_ORDER.index(level)
        ci = LEVEL_ORDER.index(ceiling)
    except ValueError:
        return level
    return level if li <= ci else ceiling


def level_bands() -> list[tuple[int, str]]:
    bands = getattr(settings, "PLACEMENT_LEVEL_MAP", None) or DEFAULT_BANDS
    # Normalise + sort by ceiling so callers can configure in any order.
    return sorted(((int(c), str(lvl)) for c, lvl in bands), key=lambda b: b[0])


def level_for_percentage(percentage) -> str:
    """Map a 0-100 percentage to a CEFR level using the configured bands."""
    try:
        pct = int(round(float(percentage or 0)))
    except (TypeError, ValueError):
        pct = 0
    pct = max(0, min(100, pct))
    bands = level_bands()
    for ceiling, level in bands:
        if pct <= ceiling:
            return level
    return bands[-1][1] if bands else "A1"


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def weighted_overall(written, speaking) -> int:
    """Blend the written + speaking percentages using the configured weights.

    Speaking weighs more than written so an easy 100/100 written sheet can't
    pull a weak speaker up to B2. Falls back to a plain 50/50 average when both
    weights are 0. Result is clamped to 0-100 and rounded to an int.
    """
    w = _to_float(written)
    s = _to_float(speaking)
    ww = _to_float(getattr(settings, "PLACEMENT_WRITTEN_WEIGHT", 0.35), 0.35)
    sw = _to_float(getattr(settings, "PLACEMENT_SPEAKING_WEIGHT", 0.65), 0.65)
    total = ww + sw
    if total <= 0:
        blended = (w + s) / 2.0
    else:
        blended = (w * ww + s * sw) / total
    return int(round(max(0.0, min(100.0, blended))))


def cap_to_speaking(final_level: str, speaking_score) -> str:
    """Lower ``final_level`` so it sits at most ``PLACEMENT_MAX_STEPS_ABOVE_SPEAKING``
    CEFR bands above the level implied by the speaking score alone.

    A perfect written sheet can nudge the level up a little, but never override
    the spoken-ability signal. Disabled (returns ``final_level`` unchanged) when
    the configured step count is >= the number of CEFR bands.
    """
    steps = int(getattr(settings, "PLACEMENT_MAX_STEPS_ABOVE_SPEAKING", 1) or 0)
    if steps >= len(LEVEL_ORDER):
        return final_level
    speaking_level = level_for_percentage(speaking_score)
    try:
        ceiling_idx = min(LEVEL_ORDER.index(speaking_level) + max(0, steps), len(LEVEL_ORDER) - 1)
    except ValueError:
        return final_level
    return cap_level(final_level, LEVEL_ORDER[ceiling_idx])


def consistent_feedback(level: str) -> str:
    """Short, level-appropriate feedback that NEVER names a different CEFR
    level — so the result page can't show "B2" next to "Estimated level: A1".
    """
    messages = {
        "A0": "You're just starting out — keep practising the basics and you'll improve quickly.",
        "A1": "You're at a beginner level. Keep building everyday words and simple sentences.",
        "A2": "You have an elementary foundation. Practise short conversations to grow your confidence.",
        "B1": "You're at an intermediate level. Keep expanding vocabulary and speaking more fluently.",
        "B2": "You're at an upper-intermediate level. Focus on nuance and longer, connected speech.",
        "C1": "You're at an advanced level. Refine precision and natural, idiomatic expression.",
        "C2": "You're at a proficient level. Keep polishing subtlety and stylistic range.",
    }
    return messages.get(level, "Keep practising — you're making progress.")
