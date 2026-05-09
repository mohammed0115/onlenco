"""Achievement evaluation + awarding.

Walks through every active Achievement and decides whether the user has
just earned it based on a snapshot + their cumulative totals across
prior snapshots.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from django.db import transaction
from django.db.models import Sum

from .. import constants as C
from ..models import Achievement, LearnerActivitySnapshot, UserAchievement
from . import xp_service


CEFR_ORDER = ["A0", "A1", "A2", "B1", "B2", "C1", "C2", "C3"]


def _cefr_at_or_above(level: str, target: str) -> bool:
    try:
        return CEFR_ORDER.index((level or "").upper()) >= CEFR_ORDER.index(target.upper())
    except ValueError:
        return False


def _cumulative_for(user, field: str, up_to_snapshot: LearnerActivitySnapshot) -> int:
    qs = LearnerActivitySnapshot.objects.filter(
        user=user, date__lte=up_to_snapshot.date
    )
    return int(qs.aggregate(s=Sum(field))["s"] or 0)


def _already_earned(user, achievement: Achievement) -> bool:
    return UserAchievement.objects.filter(user=user, achievement=achievement).exists()


def _matches(achievement: Achievement, user, snap: LearnerActivitySnapshot) -> bool:
    cat = achievement.category
    threshold = achievement.threshold_value or 0
    code = achievement.code

    if cat == C.CAT_LESSON:
        total = _cumulative_for(user, "lessons_completed", snap)
        return total >= threshold

    if cat == C.CAT_AI_TUTOR:
        # Cumulative messages divided by ~20 == "conversations" approx.
        total_msgs = _cumulative_for(user, "ai_messages_count", snap)
        conversations = max(1, total_msgs // 20) if total_msgs else 0
        return conversations >= threshold

    if cat == C.CAT_SPEAKING:
        total = _cumulative_for(user, "speaking_minutes", snap)
        return total >= threshold

    if cat == C.CAT_QUIZ:
        if code == "quiz_master_high_accuracy":
            total_q = _cumulative_for(user, "questions_answered", snap)
            return total_q >= 20 and (snap.quiz_accuracy or 0) >= threshold
        if code == "first_weekly_assessment":
            total = _cumulative_for(user, "weekly_assessments_completed", snap)
            return total >= threshold
        total = _cumulative_for(user, "questions_answered", snap)
        return total >= threshold

    if cat == C.CAT_READING:
        total = _cumulative_for(user, "words_read", snap)
        return total >= threshold

    if cat == C.CAT_STREAK:
        if code == "comeback_learner":
            # Earned when a user returns after >= 3 inactive days.
            return (snap.inactive_days or 0) == 0 and _is_returning(user, snap)
        return (snap.current_streak_days or 0) >= threshold

    if cat == C.CAT_VOCABULARY:
        total = _cumulative_for(user, "vocabulary_words_learned", snap)
        return total >= threshold

    if cat == C.CAT_LEVEL:
        target = code.replace("level_up_", "").upper()
        return _cefr_at_or_above(snap.cefr_level, target)

    if cat == C.CAT_SUBSCRIPTION:
        prof = getattr(user, "profile", None)
        return bool(prof and getattr(prof, "subscription_status", "") == "active")

    return False


def _is_returning(user, snap: LearnerActivitySnapshot) -> bool:
    prev = (
        LearnerActivitySnapshot.objects
        .filter(user=user, date__lt=snap.date)
        .order_by("-date")
        .first()
    )
    if not prev:
        return False
    return (snap.date - prev.date).days >= 3


def evaluate_for_snapshot(snap: LearnerActivitySnapshot) -> List[UserAchievement]:
    """Award every newly-earned achievement based on this snapshot."""
    earned: List[UserAchievement] = []
    user = snap.user
    for ach in Achievement.objects.filter(is_active=True):
        if _already_earned(user, ach):
            continue
        try:
            if _matches(ach, user, snap):
                ua = _award(user, ach, snap)
                if ua is not None:
                    earned.append(ua)
        except Exception:
            continue
    return earned


def _award(user, achievement: Achievement, snap: LearnerActivitySnapshot) -> Optional[UserAchievement]:
    with transaction.atomic():
        ua, created = UserAchievement.objects.get_or_create(
            user=user,
            achievement=achievement,
            defaults={"source_snapshot": snap},
        )
    if not created:
        return None
    if achievement.xp_reward:
        xp_service.award_xp(user, achievement.xp_reward, reason=f"achievement {achievement.code}")
    return ua


def award_by_code(user, code: str, snap: Optional[LearnerActivitySnapshot] = None) -> Tuple[Optional[UserAchievement], bool]:
    """Manually award an achievement by code (used by integration hooks)."""
    try:
        ach = Achievement.objects.get(code=code, is_active=True)
    except Achievement.DoesNotExist:
        return None, False
    if _already_earned(user, ach):
        return None, False
    with transaction.atomic():
        ua = UserAchievement.objects.create(user=user, achievement=ach, source_snapshot=snap)
    if ach.xp_reward:
        xp_service.award_xp(user, ach.xp_reward, reason=f"achievement {ach.code}")
    return ua, True
