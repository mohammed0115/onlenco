"""Trigger rules — what kind of motivation event should fire today?

Each rule consumes a snapshot and returns either None or a dict
describing the event to fire (message_type, payload). The engine then
asks message_generator + notifications.NotificationService to do the work.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from django.utils import timezone

from .. import constants as C
from ..models import LearnerActivitySnapshot, MotivationMessage, MotivationPreference


def _emails_today(user) -> int:
    today = timezone.localdate()
    return MotivationMessage.objects.filter(
        user=user,
        sent_via__in=[C.VIA_EMAIL, C.VIA_BOTH],
        sent_at__date=today,
    ).count()


def _weekly_summaries_this_week(user) -> int:
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    return MotivationMessage.objects.filter(
        user=user,
        message_type=C.MSG_WEEKLY_SUMMARY,
        created_at__date__gte=monday,
    ).count()


def can_email(user) -> bool:
    pref, _ = MotivationPreference.objects.get_or_create(user=user)
    if not pref.enable_email_motivation:
        return False
    return _emails_today(user) < C.MAX_EMAILS_PER_DAY


def can_email_weekly_summary(user) -> bool:
    pref, _ = MotivationPreference.objects.get_or_create(user=user)
    if not (pref.enable_email_motivation and pref.enable_weekly_summary):
        return False
    return _weekly_summaries_this_week(user) < C.MAX_WEEKLY_SUMMARY


# ---------- individual rules ----------

def rule_streak_milestone(snap: LearnerActivitySnapshot) -> Optional[dict]:
    days = snap.current_streak_days or 0
    if days in C.STREAK_MILESTONES:
        return {
            "type": C.MSG_STREAK,
            "event": "streak_milestone",
            "payload": {"days": days},
        }
    return None


def rule_inactive_comeback(snap: LearnerActivitySnapshot) -> Optional[dict]:
    inactive = snap.inactive_days or 0
    if C.INACTIVITY_COMEBACK_MIN <= inactive <= C.INACTIVITY_COMEBACK_MAX:
        return {
            "type": C.MSG_COMEBACK,
            "event": "comeback_reminder",
            "payload": {"inactive_days": inactive},
        }
    return None


def rule_high_activity(snap: LearnerActivitySnapshot) -> Optional[dict]:
    xp_today = (snap.metadata or {}).get("xp_awarded", 0)
    if xp_today >= C.TONE_FOR_HIGH_ACTIVITY_XP:
        return {
            "type": C.MSG_ENCOURAGEMENT,
            "event": "xp_awarded",
            "payload": {
                "xp": xp_today,
                "reason": "today's progress",
            },
        }
    return None


def rule_low_accuracy(snap: LearnerActivitySnapshot) -> Optional[dict]:
    """Gentle nudge when accuracy is low but the learner is showing up."""
    if (snap.questions_answered or 0) >= 10 and (snap.quiz_accuracy or 0) < 50:
        return {
            "type": C.MSG_ENCOURAGEMENT,
            "event": "motivation_message",
            "payload": {"reason": "low_accuracy"},
        }
    return None


def rule_no_activity(snap: LearnerActivitySnapshot) -> Optional[dict]:
    """User logged a snapshot but did almost nothing — quiet warning."""
    if (snap.inactive_days or 0) >= 1:
        return None  # comeback rule covers this
    if (snap.lessons_completed or 0) == 0 and (snap.questions_answered or 0) == 0:
        return {
            "type": C.MSG_WARNING,
            "event": "motivation_message",
            "payload": {"reason": "no_activity"},
        }
    return None


def evaluate_all(snap: LearnerActivitySnapshot) -> List[dict]:
    """Run every rule, return list of fired events (in priority order)."""
    fired: List[dict] = []
    for rule in (
        rule_streak_milestone,
        rule_inactive_comeback,
        rule_high_activity,
        rule_low_accuracy,
        rule_no_activity,
    ):
        try:
            res = rule(snap)
            if res:
                fired.append(res)
        except Exception:
            continue
    return fired
