"""Build a short bilingual motivation line for the day's plan."""
from __future__ import annotations

from datetime import date as _date

from . import a0_templates
from . import level_templates


def motivation_message(
    *,
    cefr_level: str,
    language: str,
    on_date: _date,
    user_id: int | None = None,
    plan_type: str = "normal_daily_plan",
) -> str:
    """Pick a short, level-appropriate motivation line.

    Deterministic on (date, user_id) so the same student doesn't
    see the same line two days in a row.
    """
    idx = on_date.toordinal() + (user_id or 0)
    level = (cefr_level or "A1").upper()

    if level == "A0":
        pool = a0_templates.A0_MOTIVATIONS_AR if language == "ar" else a0_templates.A0_MOTIVATIONS_EN
        if plan_type == "streak_recovery":
            # Comeback-tone fallback line
            return (
                "نحن سعداء بعودتك. درس قصير اليوم يكفي."
                if language == "ar"
                else "We're glad you're back. One short lesson is enough today."
            )
        return pool[idx % len(pool)]

    if plan_type == "streak_recovery":
        return (
            "اشتقنا لك! درس قصير اليوم يكفي للعودة."
            if language == "ar"
            else "We missed you! One short lesson is enough to restart."
        )
    return level_templates.motivation_line(cefr_level=level, language=language, index=idx)
