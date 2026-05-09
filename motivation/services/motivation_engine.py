"""Public orchestrator for the motivation system.

`run_for_user(user, date)` is the canonical entry point. It collects a
snapshot, awards XP, evaluates achievements, fires triggers, and emits
notification events. The dashboard widget reads MotivationMessage rows
directly from the DB.
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Optional

from django.utils import timezone

from notifications import constants as NC
from notifications.services.notification_service import NotificationService

from .. import constants as C
from ..models import (
    LearnerActivitySnapshot,
    MotivationMessage,
    MotivationPreference,
    UserAchievement,
    UserBadge,
    UserXP,
)
from . import (
    achievement_service,
    activity_collector,
    badge_service,
    challenge_service,
    message_generator,
    motivation_rules,
    xp_service,
)

logger = logging.getLogger(__name__)


def _user_pref(user) -> MotivationPreference:
    pref, _ = MotivationPreference.objects.get_or_create(user=user)
    return pref


def _emit(event_type: str, *, user, payload: dict, message: Optional[MotivationMessage] = None) -> None:
    """Send via NotificationService — preferences are honored there too."""
    try:
        svc = NotificationService()
        svc.trigger(event_type, user=user, payload=payload)
        if message is not None:
            message.status = C.STATUS_SENT
            message.sent_via = C.VIA_BOTH if message.sent_via == C.VIA_IN_APP else C.VIA_EMAIL
            message.sent_at = timezone.now()
            message.save(update_fields=["status", "sent_via", "sent_at"])
    except Exception as e:
        logger.exception("emit %s failed: %s", event_type, e)


def _emit_in_app_only(message: MotivationMessage) -> None:
    message.status = C.STATUS_SENT
    message.sent_via = C.VIA_IN_APP
    message.sent_at = timezone.now()
    message.save(update_fields=["status", "sent_via", "sent_at"])


def _payload_from_snapshot(snap: LearnerActivitySnapshot) -> dict:
    return {
        "speaking_minutes": snap.speaking_minutes,
        "ai_chat_minutes": snap.ai_chat_minutes,
        "words_read": snap.words_read,
        "lessons_completed": snap.lessons_completed,
        "questions_answered": snap.questions_answered,
        "quiz_accuracy": round(snap.quiz_accuracy or 0, 1),
        "streak_days": snap.current_streak_days,
        "xp_earned": (snap.metadata or {}).get("xp_awarded", 0),
        "summary_message": "",
    }


# ---------- public API ----------

def run_for_user(user, date: Optional[_date] = None) -> dict:
    """Run the full motivation pipeline for one user on one day."""
    if date is None:
        date = timezone.localdate()

    pref = _user_pref(user)
    snap = activity_collector.collect_daily_activity(user, date)
    xp_total, xp_breakdown, user_xp = xp_service.award_for_snapshot(snap)

    awarded_achievements = achievement_service.evaluate_for_snapshot(snap)
    awarded_badges = []

    # Tick challenge progress so opt-in goals advance every time the
    # engine fires (which is on every quiz / exam / tutor message).
    try:
        challenge_progress = challenge_service.tick_for_user(user)
    except Exception:
        logger.exception("challenge tick failed for %s", user.pk)
        challenge_progress = []

    # Streak milestone → award badge
    streak_spec = badge_service.streak_badge_for(snap.current_streak_days or 0)
    if streak_spec:
        badge, created = badge_service.award_badge(
            user,
            badge_code=streak_spec["code"],
            badge_name=streak_spec["name"],
            description=f"Studied {snap.current_streak_days} days in a row.",
            metadata={"days": snap.current_streak_days},
        )
        if created:
            awarded_badges.append(badge)

    fired_events = motivation_rules.evaluate_all(snap) if pref.enable_motivation_notifications else []

    # 1. Achievement-unlocked emails (one per achievement, never frequency-capped)
    for ua in awarded_achievements:
        msg = message_generator.build_message(
            user,
            message_type=C.MSG_ACHIEVEMENT,
            snap=snap,
            achievement=ua.achievement,
            related_activity=ua.achievement.category,
        )
        if pref.enable_email_motivation:
            _emit(
                NC.ACHIEVEMENT_UNLOCKED,
                user=user,
                payload={
                    "achievement_name": ua.achievement.name,
                    "achievement_name_ar": ua.achievement.name_ar,
                    "description": ua.achievement.description,
                    "description_ar": ua.achievement.description_ar,
                    "xp_reward": ua.achievement.xp_reward,
                    "category": ua.achievement.category,
                },
                message=msg,
            )
        else:
            _emit_in_app_only(msg)

    # 2. Badge-earned emails
    for badge in awarded_badges:
        if pref.enable_email_motivation:
            _emit(
                NC.BADGE_EARNED,
                user=user,
                payload={
                    "badge_name": badge.badge_name,
                    "badge_code": badge.badge_code,
                    "description": badge.description,
                },
            )

    # 3. Rule-fired events (frequency-capped to MAX_EMAILS_PER_DAY)
    for fired in fired_events:
        msg = message_generator.build_message(
            user,
            message_type=fired["type"],
            snap=snap,
            extra=fired.get("payload", {}),
            related_activity=fired.get("event", ""),
        )
        if pref.enable_email_motivation and motivation_rules.can_email(user):
            event_name = _event_name_for(fired["event"])
            payload = {**fired.get("payload", {}), **_payload_from_snapshot(snap)}
            _emit(event_name, user=user, payload=payload, message=msg)
        else:
            _emit_in_app_only(msg)

    return {
        "snapshot_id": snap.id,
        "xp_awarded": xp_total,
        "achievements": [ua.achievement.code for ua in awarded_achievements],
        "badges": [b.badge_code for b in awarded_badges],
        "events_fired": [f["event"] for f in fired_events],
        "challenges": [
            {"code": p.challenge.code,
             "value": p.current_value,
             "target": p.challenge.target_value,
             "complete": p.completed_at is not None}
            for p in challenge_progress
        ],
    }


def _event_name_for(rule_event: str) -> str:
    mapping = {
        "streak_milestone": NC.STREAK_MILESTONE,
        "comeback_reminder": NC.COMEBACK_REMINDER,
        "xp_awarded": NC.XP_AWARDED,
        "motivation_message": NC.MOTIVATION_MESSAGE_GENERATED,
    }
    return mapping.get(rule_event, NC.MOTIVATION_MESSAGE_GENERATED)


def run_weekly_summary(user, date: Optional[_date] = None) -> Optional[MotivationMessage]:
    """Build + email a weekly summary for one user."""
    if date is None:
        date = timezone.localdate()
    pref = _user_pref(user)
    if not pref.enable_weekly_summary:
        return None

    from datetime import timedelta
    monday = date - timedelta(days=date.weekday())
    snaps = LearnerActivitySnapshot.objects.filter(
        user=user, date__gte=monday, date__lte=date
    )
    if not snaps.exists():
        return None

    totals = {
        "speaking_minutes": 0,
        "ai_chat_minutes": 0,
        "words_read": 0,
        "lessons_completed": 0,
        "questions_answered": 0,
        "correct_answers": 0,
        "xp_earned": 0,
    }
    for s in snaps:
        totals["speaking_minutes"] += s.speaking_minutes or 0
        totals["ai_chat_minutes"] += s.ai_chat_minutes or 0
        totals["words_read"] += s.words_read or 0
        totals["lessons_completed"] += s.lessons_completed or 0
        totals["questions_answered"] += s.questions_answered or 0
        totals["correct_answers"] += s.correct_answers or 0
        totals["xp_earned"] += (s.metadata or {}).get("xp_awarded", 0)

    accuracy = (
        round(totals["correct_answers"] / totals["questions_answered"] * 100, 1)
        if totals["questions_answered"] else 0
    )
    streak_days = snaps.order_by("-date").first().current_streak_days or 0

    payload = {
        **totals,
        "quiz_accuracy": accuracy,
        "streak_days": streak_days,
        "summary_message": "",
    }

    msg = message_generator.build_message(
        user,
        message_type=C.MSG_WEEKLY_SUMMARY,
        extra=payload,
        related_activity="weekly_summary",
    )

    if pref.enable_email_motivation and motivation_rules.can_email_weekly_summary(user):
        _emit(NC.WEEKLY_MOTIVATION_SUMMARY, user=user, payload=payload, message=msg)
    else:
        _emit_in_app_only(msg)
    return msg


def run_for_all_users(date: Optional[_date] = None) -> dict:
    """Cron-style entry point — run engine for every active user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if date is None:
        date = timezone.localdate()
    summary = {"users": 0, "ok": 0, "errors": 0, "details": []}
    for user in User.objects.filter(is_active=True).iterator():
        summary["users"] += 1
        try:
            res = run_for_user(user, date)
            summary["ok"] += 1
            summary["details"].append({"user": user.pk, **res})
        except Exception as e:
            summary["errors"] += 1
            logger.exception("run_for_user failed for %s: %s", user.pk, e)
    return summary
