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
