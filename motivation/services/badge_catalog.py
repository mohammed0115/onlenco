"""Badge catalog + evaluator — Phase 5.

The existing `motivation.services.badge_service.award_badge` keeps the
UserBadge ledger atomic + idempotent. This module sits ABOVE it:

  * Reads BadgeDefinition rows (the catalog).
  * After a Challenge ends, evaluates each candidate badge against the
    student's history.
  * If the badge fires, awards it + credits any catalog `xp_reward`
    once via the XP ledger.

Adding a new badge = adding a new BadgeDefinition row (via the seed
command) + (if non-trivial) a new clause in `_evaluators`.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction

from ..models import BadgeDefinition, UserBadge
from . import badge_service as legacy_badge
from . import streak_v2


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seed catalog — used by `seed_badge_definitions` management command.
# Each entry is upserted by `code`.
# ---------------------------------------------------------------------------

DEFAULT_BADGES = [
    {
        "code": "FIRST_CHALLENGE",
        "title_en": "First Challenge",
        "title_ar": "أول تحدي",
        "description_en": "Completed your very first Challenge.",
        "description_ar": "أكملت أول تحدي لك.",
        "icon_name": "trophy",
        "xp_reward": 0,
        "criteria": {"first_completion": True},
    },
    {
        "code": "FIRST_LESSON",
        "title_en": "First Lesson",
        "title_ar": "أول درس",
        "description_en": "Completed your first lesson on Onlenco.",
        "description_ar": "أكملت أول درس لك في Onlenco.",
        "icon_name": "book-open",
        "xp_reward": 50,
        "criteria": {"first_lesson": True},
    },
    {
        "code": "PERFECT_CHALLENGE",
        "title_en": "Perfect Challenge",
        "title_ar": "تحدٍ مثالي",
        "description_en": "Finished a Challenge with zero mistakes.",
        "description_ar": "أنهيت تحدياً بدون أي خطأ.",
        "icon_name": "sparkles",
        "xp_reward": 25,
        "criteria": {"perfect_session": True},
    },
    {
        "code": "FIVE_CHALLENGES",
        "title_en": "Five Challenges",
        "title_ar": "خمسة تحديات",
        "description_en": "Completed five Challenges.",
        "description_ar": "أكملت خمسة تحديات.",
        "icon_name": "medal",
        "xp_reward": 50,
        "criteria": {"completion_count": 5},
    },
    {
        "code": "SEVEN_DAY_STREAK",
        "title_en": "7-Day Streak",
        "title_ar": "سلسلة 7 أيام",
        "description_en": "Learned every day for a week straight.",
        "description_ar": "تعلّمت يومياً لأسبوع كامل.",
        "icon_name": "flame",
        "xp_reward": 50,
        "criteria": {"streak_days": 7},
    },
    {
        "code": "LISTENING_STAR",
        "title_en": "Listening Star",
        "title_ar": "نجم الاستماع",
        "description_en": "Answered 10 listening questions correctly.",
        "description_ar": "أجبت على 10 أسئلة استماع بشكل صحيح.",
        "icon_name": "headphones",
        "xp_reward": 25,
        "criteria": {"correct_skill": "listening", "count": 10},
    },
    {
        "code": "SPEAKING_BRAVE",
        "title_en": "Speaking Brave",
        "title_ar": "شجاع المحادثة",
        "description_en": "Completed 5 speaking practice cards.",
        "description_ar": "أكملت 5 بطاقات تدريب محادثة.",
        "icon_name": "mic",
        "xp_reward": 25,
        "criteria": {"speaking_placeholders": 5},
    },
    {
        "code": "VOCAB_HERO",
        "title_en": "Vocab Hero",
        "title_ar": "بطل المفردات",
        "description_en": "Answered 20 vocabulary questions correctly.",
        "description_ar": "أجبت على 20 سؤال مفردات بشكل صحيح.",
        "icon_name": "book",
        "xp_reward": 25,
        "criteria": {"correct_skill": "vocabulary", "count": 20},
    },
    {
        "code": "GRAMMAR_BUILDER",
        "title_en": "Grammar Builder",
        "title_ar": "بنّاء القواعد",
        "description_en": "Answered 20 grammar questions correctly.",
        "description_ar": "أجبت على 20 سؤال قواعد بشكل صحيح.",
        "icon_name": "wrench",
        "xp_reward": 25,
        "criteria": {"correct_skill": "grammar", "count": 20},
    },
    {
        "code": "COMEBACK_LEARNER",
        "title_en": "Comeback Learner",
        "title_ar": "العودة القوية",
        "description_en": "Returned after 3+ days away and finished a Challenge.",
        "description_ar": "عدت بعد غياب 3 أيام أو أكثر وأكملت تحدياً.",
        "icon_name": "rotate-ccw",
        "xp_reward": 25,
        "criteria": {"comeback_days": 3},
    },
]


def seed_default_badges() -> tuple[int, int]:
    """Upsert the default catalog. Returns (created, updated)."""
    created, updated = 0, 0
    for spec in DEFAULT_BADGES:
        obj, was_new = BadgeDefinition.objects.update_or_create(
            code=spec["code"],
            defaults={k: v for k, v in spec.items() if k != "code"},
        )
        created += int(was_new)
        updated += int(not was_new)
    return created, updated


# ---------------------------------------------------------------------------
# Awarding
# ---------------------------------------------------------------------------

def award_badge(
    user,
    badge_code: str,
    *,
    source_type: str = "",
    source_id: str | int = "",
    metadata: Optional[dict] = None,
) -> tuple[Optional[UserBadge], bool]:
    """Award a single badge by `code`. Returns (UserBadge, was_new).

    Catalog lookup → ledger insert (UserBadge UNIQUE prevents dups) →
    credit xp_reward (if any) via XP ledger keyed by badge_code.
    """
    spec = BadgeDefinition.objects.filter(code=badge_code, is_active=True).first()
    if spec is None:
        return None, False
    badge, was_new = legacy_badge.award_badge(
        user,
        badge_code=spec.code,
        badge_name=spec.title_en,
        description=spec.description_en,
        metadata={**(metadata or {}), "icon": spec.icon_name},
    )
    if was_new and spec.xp_reward:
        from . import xp_ledger
        xp_ledger.award_xp(
            user, spec.xp_reward,
            source_type="badge_reward",
            source_id=spec.code,
            reason=f"badge:{spec.code}",
            metadata={
                "badge_code": spec.code,
                "source_type": source_type,
                "source_id": str(source_id),
            },
        )
    return badge, was_new


# ---------------------------------------------------------------------------
# Evaluator — runs once after each Challenge ends.
# ---------------------------------------------------------------------------

@transaction.atomic
def evaluate_badges_after_challenge(user, session) -> list[UserBadge]:
    """Check every badge whose criteria depend on Challenge outcomes.

    Returns the list of NEWLY-awarded UserBadge rows (so the Summary
    can show them inline).
    """
    awarded: list[UserBadge] = []
    earned_codes = set(
        UserBadge.objects.filter(user=user).values_list("badge_code", flat=True)
    )
    # Pre-load fresh counts.
    from courses.models import ChallengeSession, ChallengeAnswer

    completed_count = ChallengeSession.objects.filter(
        user=user, status="completed",
    ).count()

    # ---- FIRST_CHALLENGE ----
    if (
        "FIRST_CHALLENGE" not in earned_codes
        and completed_count >= 1
        and session.status == "completed"
    ):
        b, was_new = award_badge(
            user, "FIRST_CHALLENGE",
            source_type="challenge_session", source_id=session.pk,
        )
        if was_new: awarded.append(b); earned_codes.add("FIRST_CHALLENGE")

    # ---- PERFECT_CHALLENGE ----
    if (
        "PERFECT_CHALLENGE" not in earned_codes
        and session.status == "completed"
        and session.wrong_count == 0
        and session.total_questions >= 1
    ):
        b, was_new = award_badge(
            user, "PERFECT_CHALLENGE",
            source_type="challenge_session", source_id=session.pk,
        )
        if was_new: awarded.append(b); earned_codes.add("PERFECT_CHALLENGE")

    # ---- FIVE_CHALLENGES ----
    if (
        "FIVE_CHALLENGES" not in earned_codes
        and completed_count >= 5
    ):
        b, was_new = award_badge(
            user, "FIVE_CHALLENGES",
            source_type="challenge_session", source_id=session.pk,
        )
        if was_new: awarded.append(b); earned_codes.add("FIVE_CHALLENGES")

    # ---- SEVEN_DAY_STREAK ----
    streak = streak_v2.get_streak(user)
    if (
        "SEVEN_DAY_STREAK" not in earned_codes
        and streak.current_streak >= 7
    ):
        b, was_new = award_badge(
            user, "SEVEN_DAY_STREAK",
            source_type="streak", source_id=streak.current_streak,
        )
        if was_new: awarded.append(b); earned_codes.add("SEVEN_DAY_STREAK")

    # ---- Skill-based badges (LISTENING_STAR / VOCAB_HERO / GRAMMAR_BUILDER) ----
    from courses.services import question_type_registry as qtr
    skill_codes = {
        "listening": "LISTENING_STAR",
        "vocabulary": "VOCAB_HERO",
        "grammar":    "GRAMMAR_BUILDER",
    }
    skill_thresholds = {
        "LISTENING_STAR":  10,
        "VOCAB_HERO":      20,
        "GRAMMAR_BUILDER": 20,
    }
    # Count correct ChallengeAnswers grouped by skill (via session→user).
    correct_qs = ChallengeAnswer.objects.filter(
        session__user=user, is_correct=True,
    )
    # Map each answer's question_type → skill set via the registry.
    skill_counts = {"listening": 0, "vocabulary": 0, "grammar": 0,
                    "speaking": 0, "reading": 0, "writing": 0}
    speaking_placeholder_count = 0
    for ans in correct_qs.select_related("question"):
        qt = ans.question.question_type
        spec = qtr.get_spec(qt) or {}
        for s in (spec.get("skill") or []):
            if s in skill_counts:
                skill_counts[s] += 1
        if spec.get("placeholder") and "speaking" in (spec.get("skill") or []):
            speaking_placeholder_count += 1
    for skill, count in skill_counts.items():
        code = skill_codes.get(skill)
        if not code or code in earned_codes:
            continue
        if count >= skill_thresholds[code]:
            b, was_new = award_badge(
                user, code,
                source_type="skill_count", source_id=skill,
            )
            if was_new: awarded.append(b); earned_codes.add(code)

    # ---- SPEAKING_BRAVE ----
    if (
        "SPEAKING_BRAVE" not in earned_codes
        and speaking_placeholder_count >= 5
    ):
        b, was_new = award_badge(
            user, "SPEAKING_BRAVE",
            source_type="speaking_placeholders", source_id="lifetime",
        )
        if was_new: awarded.append(b); earned_codes.add("SPEAKING_BRAVE")

    # ---- COMEBACK_LEARNER ----
    # If the streak just rebooted from 0/Nthen-ago to 1 today AFTER ≥3-day gap.
    if (
        "COMEBACK_LEARNER" not in earned_codes
        and session.status == "completed"
        and _is_comeback(user, session)
    ):
        b, was_new = award_badge(
            user, "COMEBACK_LEARNER",
            source_type="comeback", source_id=session.pk,
        )
        if was_new: awarded.append(b); earned_codes.add("COMEBACK_LEARNER")

    return awarded


def _is_comeback(user, session) -> bool:
    """True if the user had a 3+ day gap immediately before today."""
    from datetime import timedelta
    from django.utils import timezone
    today = timezone.localdate()
    from ..models import StreakActivity
    # Find the previous counting activity before today.
    prev = (
        StreakActivity.objects
        .filter(user=user, activity_date__lt=today,
                activity_type__in=streak_v2.COUNTING_TYPES)
        .order_by("-activity_date")
        .first()
    )
    if prev is None:
        return False
    return (today - prev.activity_date) >= timedelta(days=3)


