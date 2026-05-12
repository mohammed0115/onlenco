"""Pick content for a daily plan, cheapest first.

Source preference order (per item slot):
  1. AdaptiveExercise rows from learning_core, filtered by CEFR level,
     skill, and difficulty, excluding what the user has already attempted.
  2. DictionaryEntry rows from `dictionary`, for vocabulary slots.
  3. Hand-curated TopicTemplate items (A0 + per-level fallbacks).

This module returns *plain dicts* describing the item — the orchestrator
turns them into DailyLearningItem instances. Keeping selection
separate from persistence makes it easy to unit-test.
"""
from __future__ import annotations

import logging
import random
from typing import Iterable

from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def _normalize_difficulty_for_level(cefr_level: str) -> tuple[float, float]:
    """Return (min, max) difficulty appropriate for the level."""
    table = {
        "A0": (0.0, 0.2),
        "A1": (0.1, 0.35),
        "A2": (0.25, 0.5),
        "B1": (0.4, 0.65),
        "B2": (0.55, 0.8),
        "C1": (0.7, 0.9),
        "C2": (0.8, 1.0),
        "C3": (0.8, 1.0),
    }
    return table.get((cefr_level or "").upper(), (0.2, 0.5))


def pick_question_from_bank(
    *,
    user,
    cefr_level: str,
    skill: str | None = None,
    grammar_topic_slug: str | None = None,
    exclude_ids: Iterable[int] = (),
) -> dict | None:
    """Pull one AdaptiveExercise that fits and the user hasn't attempted.

    Returns a plain dict describing a DailyLearningItem, or None when
    the bank can't satisfy this slot.
    """
    try:
        from learning_core.models import AdaptiveExercise, ExerciseAttempt
    except Exception:
        return None

    min_d, max_d = _normalize_difficulty_for_level(cefr_level)
    qs = AdaptiveExercise.objects.filter(
        is_active=True,
        cefr_level=cefr_level,
        difficulty_score__gte=min_d,
        difficulty_score__lte=max_d,
    )
    if skill:
        # Skill is FK; match by category name.
        qs = qs.filter(skill__category=skill) if skill != "mixed" else qs
    if grammar_topic_slug:
        qs = qs.filter(topic__slug=grammar_topic_slug)

    # Exclude already-attempted exercises (for this user).
    attempted_ids = ExerciseAttempt.objects.filter(
        user=user
    ).values_list("exercise_id", flat=True)
    qs = qs.exclude(id__in=list(attempted_ids))
    if exclude_ids:
        qs = qs.exclude(id__in=list(exclude_ids))

    # Prefer reviewed > unreviewed; randomise within tier so different
    # students get different items.
    ex = qs.filter(is_reviewed=True).order_by("?").first()
    if not ex:
        ex = qs.order_by("?").first()
    if not ex:
        return None

    # Convert AdaptiveExercise → DailyLearningItem dict
    item_type = _question_type_to_item_type(ex.question_type)
    return {
        "item_type": item_type,
        "title": f"Quick {ex.question_type.replace('_', ' ')}",
        "instructions": _student_instruction_for(item_type, ex.question_type),
        "content_text": "",
        "question": ex.question,
        "options": list(ex.options or []),
        "correct_answer": ex.correct_answer or "",
        "explanation": ex.explanation or "",
        "cefr_level": ex.cefr_level,
        "skill": (ex.skill.category if ex.skill_id else (skill or "mixed")),
        "difficulty_score": ex.difficulty_score,
        "estimated_minutes": max(1, (ex.estimated_time_seconds or 30) // 60 + 1),
        "metadata": {
            "source": "adaptive_exercise",
            "exercise_id": ex.id,
            "question_type": ex.question_type,
        },
    }


def pick_vocabulary_item(
    *,
    user,
    cefr_level: str,
    language: str = "en",
    exclude_terms: Iterable[str] = (),
) -> dict | None:
    """Pick one DictionaryEntry as a vocabulary slot."""
    try:
        from dictionary.models import DictionaryEntry
    except Exception:
        return None

    qs = DictionaryEntry.objects.all()
    # Best-effort CEFR filter; not all entries are tagged.
    if hasattr(DictionaryEntry, "cefr_level"):
        leveled = qs.filter(cefr_level=cefr_level)
        if leveled.exists():
            qs = leveled
    if exclude_terms:
        qs = qs.exclude(english__in=list(exclude_terms))
    entry = qs.order_by("?").first()
    if not entry:
        return None

    english = getattr(entry, "english", "") or ""
    arabic = getattr(entry, "arabic", "") or ""
    example = getattr(entry, "example_en", None) or getattr(entry, "example_sentence", "") or ""
    if language == "ar" and arabic:
        title = f"كلمة اليوم: {english}"
        content = f"{english} — {arabic}"
    else:
        title = f"Word of the day: {english}"
        content = f"{english} — {arabic}" if arabic else english
    if example:
        content = f"{content}\nExample: {example}"
    return {
        "item_type": "vocabulary",
        "title": title,
        "instructions": (
            "اقرأ الكلمة وانطقها، ثم اقرأ المثال."
            if language == "ar"
            else "Read the word, say it aloud, then read the example."
        ),
        "content_text": content,
        "question": "",
        "options": [],
        "correct_answer": "",
        "explanation": "",
        "cefr_level": getattr(entry, "cefr_level", "") or cefr_level,
        "skill": "vocabulary",
        "difficulty_score": _normalize_difficulty_for_level(cefr_level)[0],
        "estimated_minutes": 1,
        "metadata": {"source": "dictionary_entry", "entry_id": entry.id},
    }


def _question_type_to_item_type(question_type: str) -> str:
    """Map learning_core.AdaptiveExercise question_type → item_type."""
    if question_type == "translation":
        return "writing"
    if question_type == "sentence_building":
        return "writing"
    if question_type == "short_answer":
        return "writing"
    if question_type == "correction":
        return "quiz"
    # multiple_choice / fill_blank / picture_* → quiz
    return "quiz"


def _student_instruction_for(item_type: str, question_type: str) -> str:
    """Friendly student-facing instruction (English; the renderer
    can swap to Arabic per the request language)."""
    if question_type == "fill_blank":
        return "Choose the word that fills the blank."
    if question_type == "multiple_choice":
        return "Pick the best answer."
    if question_type == "correction":
        return "Fix the mistake in the sentence."
    if question_type == "sentence_building":
        return "Build a correct sentence."
    if question_type == "translation":
        return "Translate the sentence."
    if question_type == "short_answer":
        return "Write a short answer."
    if question_type.startswith("picture"):
        return "Look at the picture and choose the right word."
    return "Answer the question below."
