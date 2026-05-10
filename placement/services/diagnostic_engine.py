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
    UserWeakness,
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

CORE_SKILL_NAMES = {
    "grammar": "Grammar core",
    "vocabulary": "Vocabulary core",
    "writing": "Writing core",
    "speaking": "Speaking core",
    "pronunciation": "Pronunciation core",
}


def _seed_theta_from_cefr(level: str) -> float:
    return CEFR_TO_THETA.get(level, 0.0)


def _ensure_core_skills() -> dict[str, Skill]:
    skills = {}
    for category, name in CORE_SKILL_NAMES.items():
        skill = (
            Skill.objects.filter(category=category, cefr_level="", is_active=True)
            .order_by("id")
            .first()
        )
        if not skill:
            skill, _ = Skill.objects.get_or_create(
                name=name,
                category=category,
                cefr_level="",
                defaults={"is_active": True},
            )
        skills[category] = skill
    return skills


def _skill_score_map(assessment: dict) -> dict[str, int | None]:
    return {
        "grammar": _score_or_none(assessment.get("grammar_score")),
        "vocabulary": _score_or_none(assessment.get("vocabulary_score")),
        "writing": _score_or_none(assessment.get("written_score")),
        "speaking": _score_or_none(assessment.get("speaking_score")),
        "pronunciation": _score_or_none(assessment.get("pronunciation_score")),
    }


def _score_or_none(value) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def _ensure_skill_masteries(user, assessment: dict, skills: dict[str, Skill]) -> None:
    """Seed/update skill mastery from placement dimensions."""
    scores = _skill_score_map(assessment)
    for category, skill in skills.items():
        score = scores.get(category)
        mastery = float(score if score is not None else 0)
        touched = score is not None
        SkillMastery.objects.update_or_create(
            user=user,
            skill=skill,
            defaults={
                "mastery_score": mastery,
                "attempts_count": 1 if touched else 0,
                "correct_count": 1 if touched and mastery >= 70 else 0,
                "wrong_count": 1 if touched and mastery < 70 else 0,
            },
        )


def _seed_placement_weaknesses(user, assessment: dict, skills: dict[str, Skill]) -> None:
    """Create placement weaknesses from low dimension scores.

    Error analysis can fail or produce no typed errors. Placement dimensions
    still give us enough signal to seed safe, transparent weakness rows.
    """
    scores = _skill_score_map(assessment)
    for category in ("grammar", "vocabulary", "writing", "speaking"):
        score = scores.get(category)
        skill = skills.get(category)
        if score is None or score >= 70 or skill is None:
            continue
        weakness = round(100 - score, 2)
        severity = max(1.0, min(10.0, (100 - score) / 10))
        UserWeakness.objects.update_or_create(
            user=user,
            skill=skill,
            grammar_topic=None,
            defaults={
                "weakness_score": weakness,
                "frequency": 1,
                "severity_average": round(severity, 2),
                "recency_score": 1.0,
                "priority_score": max(25.0, weakness),
                "status": "active",
            },
        )


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
            "initial_cefr_level": cefr_level,
            "written_score": written_score,
            "speaking_score": speaking_score,
            "grammar_score": raw.get("grammar_score"),
            "vocabulary_score": raw.get("vocabulary_score"),
            "fluency_score": raw.get("fluency_score"),
            "pronunciation_score": raw.get("pronunciation_score"),
            "overall_score": raw.get("overall_score"),
            "pronunciation_available": bool(raw.get("pronunciation_score") is not None),
        },
    }
    profile.save(update_fields=[
        "current_cefr_level", "theta_score", "metadata", "updated_at",
    ])

    # 2. Error analysis on free-form written answers.
    if answers.get("mode") == "dynamic":
        written_text = " ".join(
            str(item.get("answer") or "")
            for item in (answers.get("items") or [])
            if item.get("section") == "written"
            and item.get("expected_answer_type") != "mcq"
        ).strip()
    else:
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

    # 4. Initialize adaptive learning artifacts from placement dimensions.
    try:
        skills = _ensure_core_skills()
        _ensure_skill_masteries(user, raw, skills)
        _seed_placement_weaknesses(user, raw, skills)
    except Exception as e:
        logger.warning("Diagnostic engine: placement learning seed failed: %s", e)

    try:
        from learning_core.services.recommendation_engine import generate_recommendations
        generate_recommendations(user)
    except Exception as e:
        logger.warning("Diagnostic engine: recommendation generation failed: %s", e)

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
