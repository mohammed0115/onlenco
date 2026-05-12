"""Pick + persist the day's DailyGoal for a user.

Daily goals are auto-generated (not chosen by the student). They scale
with the student's level and activity history so beginners aren't asked
to read 500 words on day one. Re-running on the same (user, date) is
idempotent via the unique constraint.
"""
from __future__ import annotations

from datetime import date as _date

from django.db import IntegrityError

from ..models import DailyGoal


# (goal_type, target, reward_xp) per level family.
# Spec wants something achievable — these are intentionally easy.
_GOAL_TABLE = {
    "A0": [("answer_questions", 3,  5),  ("speaking_minutes", 2,  5)],
    "A1": [("answer_questions", 5,  10), ("speaking_minutes", 3,  10)],
    "A2": [("answer_questions", 6,  10), ("reading_words",    50, 10)],
    "B1": [("complete_lesson",  1,  15), ("reading_words",    100, 10)],
    "B2": [("complete_lesson",  1,  15), ("reading_words",    150, 10)],
    "C1": [("complete_lesson",  1,  20), ("reading_words",    200, 10)],
    "C2": [("complete_lesson",  1,  20), ("reading_words",    250, 10)],
    "C3": [("complete_lesson",  1,  20), ("reading_words",    250, 10)],
}


def ensure_daily_goal(user, on_date: _date, cefr_level: str) -> DailyGoal:
    """Create one DailyGoal for the day if none exists.

    Picks a single goal type; future passes can layer in a second one
    (e.g. streak maintenance) without breaking the unique constraint
    because that uses a different goal_type.
    """
    level = (cefr_level or "A1").upper()
    spec = _GOAL_TABLE.get(level) or _GOAL_TABLE["A1"]
    # Use date ordinal to alternate between the two goal types each day.
    goal_type, target, reward_xp = spec[on_date.toordinal() % len(spec)]
    try:
        goal, _created = DailyGoal.objects.get_or_create(
            user=user,
            date=on_date,
            goal_type=goal_type,
            defaults={"target_value": target, "reward_xp": reward_xp},
        )
    except IntegrityError:
        # Race lost — fetch the row that won the insert.
        goal = DailyGoal.objects.get(user=user, date=on_date, goal_type=goal_type)
    return goal


def ensure_streak_goal(user, on_date: _date) -> DailyGoal | None:
    """Optional second goal: maintain streak (always 1 plan/day)."""
    try:
        goal, _ = DailyGoal.objects.get_or_create(
            user=user,
            date=on_date,
            goal_type="maintain_streak",
            defaults={"target_value": 1, "reward_xp": 5},
        )
    except IntegrityError:
        goal = DailyGoal.objects.filter(
            user=user, date=on_date, goal_type="maintain_streak"
        ).first()
    return goal


def increment_goals_on_item_completion(user, on_date: _date, item) -> None:
    """Tick relevant goals when a DailyLearningItem is marked done."""
    goals = list(DailyGoal.objects.filter(user=user, date=on_date, completed=False))
    if not goals:
        return
    for g in goals:
        if g.goal_type == "answer_questions" and item.item_type in {"quiz", "review_mistake"}:
            g.current_value = min(g.current_value + 1, g.target_value)
        elif g.goal_type == "speaking_minutes" and item.item_type in {"speaking", "ai_tutor_practice"}:
            g.current_value = min(g.current_value + (item.estimated_minutes or 1), g.target_value)
        elif g.goal_type == "reading_words" and item.item_type == "reading":
            # Approximate word count from the content_text length.
            approx_words = max(20, len((item.content_text or "").split()))
            g.current_value = min(g.current_value + approx_words, g.target_value)
        elif g.goal_type == "review_mistakes" and item.item_type == "review_mistake":
            g.current_value = min(g.current_value + 1, g.target_value)
        else:
            continue
        g.completed = g.current_value >= g.target_value
        g.save(update_fields=["current_value", "completed"])
