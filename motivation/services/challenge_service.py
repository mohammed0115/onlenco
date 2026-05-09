"""Challenge service — opt-in time-boxed goals with bonus XP.

Public API:
    open_challenges(user, today=None) -> list[Challenge]
    tick_for_user(user) -> list[ChallengeProgress]      (run from engine)
    seed_default_challenges()                          (idempotent seeder)
    rotate_weekly()                                    (cron Monday 00:00)
"""
from __future__ import annotations

import logging
from datetime import date as _date, timedelta
from typing import List, Optional

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ..models import Challenge, ChallengeProgress, LearnerActivitySnapshot
from . import xp_service

logger = logging.getLogger(__name__)


def open_challenges(user=None, today: Optional[_date] = None) -> List[Challenge]:
    """Active challenges spanning `today`. `user` is reserved for future
    per-cohort filtering (currently every active challenge applies)."""
    if today is None:
        today = timezone.localdate()
    return list(
        Challenge.objects
        .filter(is_active=True, start_at__lte=today, end_at__gte=today)
        .order_by("-start_at")
    )


def _cumulative(user, metric: str, start: _date, end: _date) -> int:
    qs = LearnerActivitySnapshot.objects.filter(
        user=user, date__gte=start, date__lte=end,
    )
    field_total = qs.aggregate(s=Sum(metric)).get("s") or 0
    try:
        return int(field_total)
    except Exception:
        return 0


def tick_for_user(user) -> List[ChallengeProgress]:
    """Refresh every open challenge's progress for this user.

    Called from `motivation_engine.run_for_user` so progress updates
    follow the same hot path as XP / streaks. Awards XP exactly once
    per challenge by setting `completed_at`.
    """
    today = timezone.localdate()
    out: List[ChallengeProgress] = []
    for ch in open_challenges(user, today):
        try:
            value = _cumulative(user, ch.metric, ch.start_at, today)
        except Exception:
            continue
        with transaction.atomic():
            prog, _ = ChallengeProgress.objects.select_for_update().get_or_create(
                user=user, challenge=ch,
            )
            if prog.current_value != value:
                prog.current_value = value
                prog.save(update_fields=["current_value", "updated_at"])
            if prog.completed_at is None and value >= ch.target_value:
                prog.completed_at = timezone.now()
                prog.save(update_fields=["completed_at", "updated_at"])
                if ch.xp_reward:
                    xp_service.award_xp(
                        user, ch.xp_reward, reason=f"challenge {ch.code}"
                    )
        out.append(prog)
    return out


def seed_default_challenges() -> int:
    """Create the rolling default challenges if missing. Idempotent."""
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    first_of_month = today.replace(day=1)
    next_month = (first_of_month + timedelta(days=32)).replace(day=1)
    end_of_month = next_month - timedelta(days=1)

    seeds = [
        {
            "code": f"daily_3lessons_{today.isoformat()}",
            "title": "Three lessons today",
            "title_ar": "ثلاثة دروس اليوم",
            "description": "Complete 3 lessons before midnight to earn the badge.",
            "description_ar": "أكمل 3 دروس قبل منتصف الليل لربح الشارة.",
            "kind": "daily",
            "metric": "lessons_completed",
            "target_value": 3,
            "xp_reward": 30,
            "start_at": today,
            "end_at": today,
        },
        {
            "code": f"weekly_50q_{monday.isoformat()}",
            "title": "Answer 50 quiz questions this week",
            "title_ar": "أجب على 50 سؤالاً هذا الأسبوع",
            "description": "Reach 50 questions answered between Monday and Sunday.",
            "description_ar": "أجب على 50 سؤالاً بين الإثنين والأحد.",
            "kind": "weekly",
            "metric": "questions_answered",
            "target_value": 50,
            "xp_reward": 100,
            "start_at": monday,
            "end_at": sunday,
        },
        {
            "code": f"weekly_30speak_{monday.isoformat()}",
            "title": "Speak 30 minutes this week",
            "title_ar": "تحدث 30 دقيقة هذا الأسبوع",
            "description": "Use the AI tutor's voice mode for 30 minutes total.",
            "description_ar": "استخدم وضع الصوت في المعلم الذكي لمدة 30 دقيقة.",
            "kind": "weekly",
            "metric": "speaking_minutes",
            "target_value": 30,
            "xp_reward": 150,
            "start_at": monday,
            "end_at": sunday,
        },
        {
            "code": f"monthly_5kwords_{first_of_month.isoformat()}",
            "title": "Read 5,000 words this month",
            "title_ar": "اقرأ 5,000 كلمة هذا الشهر",
            "description": "Reach 5,000 words read across all library books.",
            "description_ar": "اقرأ 5,000 كلمة من المكتبة هذا الشهر.",
            "kind": "monthly",
            "metric": "words_read",
            "target_value": 5000,
            "xp_reward": 250,
            "start_at": first_of_month,
            "end_at": end_of_month,
        },
    ]
    created = 0
    for s in seeds:
        _, was_created = Challenge.objects.get_or_create(code=s["code"], defaults=s)
        if was_created:
            created += 1
    return created


def rotate_weekly() -> int:
    """Cron entry-point: ensure today's daily + this-week's weekly +
    this-month's monthly challenges all exist."""
    return seed_default_challenges()
