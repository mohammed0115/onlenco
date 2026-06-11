"""Mark items / plans complete, award XP, write the result row.

This is the only service that mutates `motivation.UserXP` (via
`xp_service.award_xp`). Everywhere else stays read-only on the
motivation side so we don't double-credit.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from ..models import (
    DailyLearningItem,
    DailyLearningPlan,
    DailyLearningResult,
)
from . import daily_goal_service

logger = logging.getLogger(__name__)


def mark_item_complete(
    item: DailyLearningItem, *, user_answer: str = "", grade: dict | None = None,
) -> DailyLearningItem:
    """Mark a single item as done. Idempotent.

    ``grade`` (from ``daily_grading.grade_item``) is stored additively in
    metadata so ``complete_plan`` can score by correctness (Prompt 18.3B).
    """
    if item.is_completed:
        return item
    item.is_completed = True
    item.completed_at = timezone.now()
    meta = dict(item.metadata or {})
    if user_answer:
        meta["last_answer"] = user_answer[:200]
    if grade is not None:
        meta["grade"] = int(grade.get("score", 0))
        meta["is_correct"] = bool(grade.get("is_correct"))
        meta["graded_at"] = timezone.now().isoformat()
        meta["attempt_count"] = int(meta.get("attempt_count", 0)) + 1
    item.metadata = meta
    item.save(update_fields=["is_completed", "completed_at", "metadata"])

    # Tick goals (best-effort)
    try:
        daily_goal_service.increment_goals_on_item_completion(
            item.daily_plan.user, item.daily_plan.date, item
        )
    except Exception:
        logger.exception("goal increment failed for item %s", item.id)

    # Roll plan to "in_progress" if still pending
    plan = item.daily_plan
    if plan.status == "pending":
        plan.status = "in_progress"
        plan.save(update_fields=["status"])
    return item


def complete_plan(plan: DailyLearningPlan, *, force: bool = False) -> DailyLearningResult:
    """Mark the plan complete, write a result row, award XP.

    `force=True` finalizes the plan even when some items are still
    pending — used when the student explicitly taps "Finish for today".
    """
    items = list(plan.items.all())
    total = len(items)
    done = sum(1 for i in items if i.is_completed)
    # Score by CORRECTNESS when graded items exist (Prompt 18.3B); fall back to
    # completion% for legacy plans with no per-item grades.
    plan_score = _plan_score(items, done, total)

    if not force and done < total:
        # Standard finalize: only mark complete when every item is done.
        # If not, just keep status as in_progress and return nothing new.
        result, created = DailyLearningResult.objects.get_or_create(
            user=plan.user,
            daily_plan=plan,
            defaults={
                "completed_items_count": done,
                "total_items_count": total,
                "score": plan_score,
                "xp_earned": 0,
                "streak_updated": False,
            },
        )
        return result

    score = plan_score
    xp = _xp_reward(plan, done, total)
    mistakes_reviewed = sum(
        1 for i in items
        if i.is_completed and i.item_type == "review_mistake"
    )
    weaknesses_improved = _weaknesses_touched(items)

    with transaction.atomic():
        plan.status = "completed" if done == total else "in_progress"
        plan.completed_at = timezone.now() if done == total else plan.completed_at
        plan.save(update_fields=["status", "completed_at"])

        result, created = DailyLearningResult.objects.update_or_create(
            user=plan.user,
            daily_plan=plan,
            defaults={
                "completed_items_count": done,
                "total_items_count": total,
                "score": score,
                "xp_earned": xp,
                "streak_updated": True,
                "weaknesses_improved": weaknesses_improved,
                "mistakes_reviewed": mistakes_reviewed,
            },
        )

    # Award XP via the motivation service (outside the transaction —
    # we don't want xp_service failures to roll back the plan).
    if xp > 0:
        try:
            from motivation.services import xp_service
            xp_service.award_xp(plan.user, xp, reason=f"daily_plan {plan.date}")
        except Exception:
            logger.exception("xp_service.award_xp failed for plan %s", plan.id)

    # Fire the motivation engine inline so the daily snapshot is
    # written and the streak ticks immediately — otherwise a learner
    # who only ever completes daily plans (no traditional lesson
    # views) would see their streak stuck at 0 between cron runs.
    if plan.status == "completed":
        try:
            from motivation.services.motivation_engine import run_for_user
            run_for_user(plan.user)
        except Exception:
            logger.warning(
                "motivation_engine.run_for_user failed for plan %s",
                plan.id, exc_info=True,
            )

    # Best-effort notify streak milestone after the snapshot has been
    # written by the engine above.
    try:
        _maybe_notify_streak_milestone(plan.user, plan.date)
    except Exception:
        logger.exception("streak milestone notify failed")

    # A0 → A1 graduation check. Only fires when the full plan finished;
    # never mid-day.
    if plan.cefr_level == "A0" and plan.status == "completed":
        try:
            from . import a0_progression_service
            a0_progression_service.maybe_promote_a0_to_a1(plan.user)
        except Exception:
            logger.exception("a0 promotion check failed")

    return result


def _calc_score(done: int, total: int) -> float:
    if not total:
        return 0.0
    return round(done / total * 100.0, 1)


def _plan_score(items, done: int, total: int) -> float:
    """Correctness score (Prompt 18.3B): correct_items / graded_items × 100.

    Falls back to completion% when no item carries a backend grade — keeps
    legacy plans (graded only in the old client-side flow) backward-compatible.
    """
    graded = [i for i in items if i.is_completed and "is_correct" in (i.metadata or {})]
    if not graded:
        return _calc_score(done, total)
    correct = sum(1 for i in graded if (i.metadata or {}).get("is_correct"))
    return round(correct / len(graded) * 100.0, 1)


def _xp_reward(plan: DailyLearningPlan, done: int, total: int) -> int:
    if not total or done == 0:
        return 0
    base = 5 * done                 # 5 XP per completed item
    if done == total:
        base += 10                  # completion bonus
    if plan.plan_type == "streak_recovery":
        base += 5                   # comeback bonus
    return base


def _weaknesses_touched(items: Iterable[DailyLearningItem]) -> list[int]:
    out: list[int] = []
    for i in items:
        if not i.is_completed:
            continue
        wid = (i.metadata or {}).get("weakness_id")
        if wid and wid not in out:
            out.append(int(wid))
    return out


def _maybe_notify_streak_milestone(user, on_date) -> None:
    try:
        from motivation.services import streak_service
    except Exception:
        return
    streak = streak_service.get_current_streak(user, on_date)
    if streak_service.is_streak_milestone(streak):
        # The motivation engine has its own notification side-effects.
        # We only nudge the notification system if it's available.
        try:
            from notifications import constants as Nc
            from notifications.services.notification_service import NotificationService
            NotificationService().trigger(
                Nc.STREAK_MILESTONE,
                user=user,
                payload={"streak_days": streak},
                priority=Nc.PRIORITY_NORMAL,
            )
        except Exception:
            pass
