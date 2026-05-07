"""Placement diagnostic engine.

Wraps the existing `assess()` AI scorer. After a placement submission this
service:
  1. Calls assess() to get CEFR level + scores + feedback.
  2. Initializes/updates StudentLearningProfile (theta seeded from CEFR).
  3. Runs ErrorAnalyzer on the free-form written answers (q3, q4) so
     UserError rows are created.
  4. Recomputes UserWeakness rows.
  5. Initializes SkillMastery rows for relevant skill categories.
  6. Returns a structured diagnostic dict (cefr_level, strengths,
     weaknesses, recommended_lessons, recommended_exercises).

Any AI failure falls back to the existing heuristic and never crashes.
"""
from __future__ import annotations

import logging

from django.db import transaction

from learning_core.models import (
    Skill,
    SkillMastery,
    StudentLearningProfile,
    UserError,
)
from learning_core.services.adaptive_difficulty import cefr_for_theta
from learning_core.services.error_analyzer import analyze_text
from learning_core.services.weakness_engine import update_user_weaknesses, get_top_weaknesses

from ._assessor import assess

logger = logging.getLogger(__name__)


CEFR_TO_THETA = {
    "A0": -2.7,
    "A1": -1.8,
    "A2": -0.9,
    "B1": 0.0,
    "B2": 0.9,
    "C1": 1.8,
    "C2": 2.5,
}


def _seed_theta_from_cefr(level: str) -> float:
    return CEFR_TO_THETA.get(level, 0.0)


def _ensure_skill_masteries(user) -> None:
    """Ensure a SkillMastery row exists for each active Skill (so dashboards
    don't show empty data on day 1)."""
    skills = Skill.objects.filter(is_active=True)
    rows = []
    for skill in skills:
        if not SkillMastery.objects.filter(user=user, skill=skill).exists():
            rows.append(SkillMastery(user=user, skill=skill, mastery_score=0.0))
    if rows:
        SkillMastery.objects.bulk_create(rows)


def build_diagnostic_profile(user, answers: dict, assessment: dict | None = None) -> dict:
    """Run placement diagnostics. Returns a rich dict for templates/APIs.

    If `assessment` is provided (already produced by `assess()`), it is used
    directly so we don't double-call the AI. Otherwise this calls assess().
    """
    raw = assessment if assessment is not None else assess(answers)

    cefr_level = raw.get("level") or "A2"
    written_score = raw.get("written_score") or 0
    speaking_score = raw.get("speaking_score") or 0
    feedback = raw.get("feedback", "")

    # 1. Profile + theta seed
    profile, _ = StudentLearningProfile.objects.get_or_create(user=user)
    profile.current_cefr_level = cefr_level
    profile.theta_score = _seed_theta_from_cefr(cefr_level)
    profile.metadata = {
        **(profile.metadata or {}),
        "placement": {
            "level": cefr_level,
            "written_score": written_score,
            "speaking_score": speaking_score,
        },
    }
    profile.save(update_fields=[
        "current_cefr_level", "theta_score", "metadata", "updated_at",
    ])

    # 2. Error analysis on free-form answers (q3 = hobbies, q4 = past)
    written_text = " ".join(
        [str(answers.get("q3", "") or ""), str(answers.get("q4", "") or "")]
    ).strip()
    if written_text:
        try:
            analyze_text(user, written_text, source_type="placement")
        except Exception as e:
            logger.warning("Diagnostic engine: error analyzer failed: %s", e)

    # 3. Recompute weaknesses
    try:
        update_user_weaknesses(user)
    except Exception as e:
        logger.warning("Diagnostic engine: weakness update failed: %s", e)

    # 4. Initialize skill masteries
    try:
        _ensure_skill_masteries(user)
    except Exception as e:
        logger.warning("Diagnostic engine: mastery init failed: %s", e)

    weaknesses = get_top_weaknesses(user, limit=5)
    user_errors = list(
        UserError.objects.filter(user=user, source_type="placement").order_by("-created_at")[:10]
    )

    grammar_weaknesses = [
        (w.grammar_topic.name if w.grammar_topic else (w.skill.name if w.skill else "general"))
        for w in weaknesses
    ]

    diagnostic = {
        "cefr_level": cefr_level,
        "score": written_score,
        "written_score": written_score,
        "speaking_score": speaking_score,
        "feedback": feedback,
        "grammar_strengths": _grammar_strengths(cefr_level),
        "grammar_weaknesses": grammar_weaknesses,
        "vocabulary_level": cefr_level,
        "writing_quality": _writing_quality(written_score),
        "speaking_transcript_quality": _writing_quality(speaking_score),
        "recommended_lessons": [],
        "recommended_exercises": [],
        "errors_detected": [
            {
                "fragment": ue.original_text,
                "explanation": ue.explanation,
                "severity": ue.severity,
            }
            for ue in user_errors
        ],
    }

    try:
        from notifications import constants as C
        from notifications.services import NotificationService
        NotificationService().trigger(
            C.PLACEMENT_COMPLETED,
            user=user,
            payload={
                "cefr_level": cefr_level,
                "strengths": diagnostic["grammar_strengths"],
                "weaknesses": grammar_weaknesses,
                "next_step": "Open your dashboard and start your first personalized lesson.",
                "cta_url": "/dashboard/",
                "cta_label": "Open dashboard",
                "dedup_key": f"placement:{profile.updated_at.isoformat()}",
            },
        )
    except Exception as e:
        logger.warning("placement notification failed: %s", e)

    return diagnostic


def _grammar_strengths(level: str) -> list[str]:
    table = {
        "A0": [],
        "A1": ["basic pronouns"],
        "A2": ["basic pronouns", "present simple"],
        "B1": ["present simple", "past simple"],
        "B2": ["present simple", "past simple", "present perfect"],
        "C1": ["complex tenses", "conditionals"],
        "C2": ["advanced syntax", "discourse markers"],
    }
    return table.get(level, [])


def _writing_quality(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"
