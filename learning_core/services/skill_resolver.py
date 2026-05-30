"""Map a LessonQuestion to one or more `Skill` rows.

Strategy:
  1. `question.metadata["skills"]` (list of skill codes) — preferred.
  2. `question.metadata["skill"]` (single skill code) — legacy.
  3. Inferred from the lesson — `lesson.grammar_topic` or
     `lesson.vocabulary_topic`, mapped to a skill code if seeded.
  4. Fallback: `general_beginner` — must be seeded by
     `seed_learning_skills`.

The resolver NEVER raises; if everything fails it returns an empty
list and logs a warning. The Challenge engine must still finish.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.utils.text import slugify

from ..models import Skill


logger = logging.getLogger(__name__)

FALLBACK_SKILL_CODE = "general_beginner"


def _normalise_codes(raw) -> list[str]:
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, (list, tuple)):
        return [str(c) for c in raw if c]
    return []


def get_question_skill_codes(question) -> list[str]:
    """Return the explicit skill codes attached to a question (no fallback)."""
    md = getattr(question, "metadata", None) or {}
    codes = _normalise_codes(md.get("skills"))
    if codes:
        return codes
    return _normalise_codes(md.get("skill"))


def get_question_skills(question) -> list[Skill]:
    """Resolve the question to a list of Skill rows. May include a
    fallback skill if no metadata + no inference succeeds."""
    codes = get_question_skill_codes(question)
    if not codes:
        inferred = infer_skill_from_lesson(getattr(question, "quiz", None))
        if inferred:
            codes = [inferred]
    skills = list(Skill.objects.filter(code__in=codes, is_active=True))
    if skills:
        return skills
    fallback = Skill.objects.filter(code=FALLBACK_SKILL_CODE, is_active=True).first()
    if fallback is not None:
        logger.info(
            "Skill resolver used fallback '%s' for question pk=%s",
            FALLBACK_SKILL_CODE, getattr(question, "pk", None),
        )
        return [fallback]
    logger.warning(
        "Skill resolver returned no skills for question pk=%s "
        "(metadata=%s) — fallback row '%s' not seeded.",
        getattr(question, "pk", None), get_question_skill_codes(question),
        FALLBACK_SKILL_CODE,
    )
    return []


def get_primary_skill(question) -> Optional[Skill]:
    skills = get_question_skills(question)
    return skills[0] if skills else None


def infer_skill_from_lesson(quiz_or_lesson) -> Optional[str]:
    """Best-effort code inference from `lesson.grammar_topic` /
    `lesson.vocabulary_topic`. Returns a candidate `code` slug."""
    lesson = getattr(quiz_or_lesson, "lesson", quiz_or_lesson)
    if lesson is None:
        return None
    for attr in ("grammar_topic", "vocabulary_topic"):
        raw = (getattr(lesson, attr, "") or "").strip()
        if raw:
            candidate = slugify(raw).replace("-", "_")
            if Skill.objects.filter(code=candidate, is_active=True).exists():
                return candidate
    return None


def validate_question_skills(question) -> list[str]:
    """Return a list of issues — empty list = OK. Used by management
    commands + admin validation."""
    issues: list[str] = []
    md = getattr(question, "metadata", None) or {}
    declared = _normalise_codes(md.get("skills")) or _normalise_codes(md.get("skill"))
    if not declared:
        if not infer_skill_from_lesson(getattr(question, "quiz", None)):
            issues.append("no_skill_attached_and_no_inference_possible")
    unknown = [
        c for c in declared
        if not Skill.objects.filter(code=c).exists()
    ]
    if unknown:
        issues.append(f"unknown_skill_codes:{','.join(unknown)}")
    return issues
