"""Personalized Exercise Generator.

Public entry: generate_personalized_exercises(user, count_per_weakness=5).

For each of the user's top weaknesses, ask the AI for exercises matching the
skill / grammar topic / CEFR level / target difficulty. If AI is not
configured or fails, fall back to local templates. Persist as AdaptiveExercise.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

import requests
from django.conf import settings
from django.db import transaction

from learning_core.models import (
    QUESTION_TYPE_CHOICES,
    AdaptiveExercise,
    GrammarTopic,
    Skill,
    StudentLearningProfile,
)

from . import exercise_templates
from .adaptive_difficulty import recommend_next_difficulty
from .prompts import (
    EXERCISE_GEN_SYSTEM,
    EXERCISE_GEN_TOOL,
    build_exercise_gen_user_prompt,
)
from .weakness_engine import get_top_weaknesses

logger = logging.getLogger(__name__)

PROMPT_VERSION = "exgen-v1"
ALLOWED_QUESTION_TYPES = {choice[0] for choice in QUESTION_TYPE_CHOICES}


def generate_personalized_exercises(user, count_per_weakness: int = 5) -> list[AdaptiveExercise]:
    profile, _ = StudentLearningProfile.objects.get_or_create(user=user)
    weaknesses = get_top_weaknesses(user, limit=3)
    target_difficulty = recommend_next_difficulty(user, target_p=0.7)

    saved: list[AdaptiveExercise] = []

    if not weaknesses:
        # No weaknesses yet → generate a small generic warm-up batch
        saved.extend(
            _build_and_save_batch(
                skill=None,
                topic=None,
                cefr_level=profile.current_cefr_level or "A2",
                difficulty=target_difficulty,
                count=count_per_weakness,
                user=user,
            )
        )
        _notify_exercises_generated(user, saved, target_difficulty)
        return saved

    seen_questions: set[str] = set()
    for w in weaknesses:
        cefr = (
            (w.skill.cefr_level if w.skill else None)
            or (w.grammar_topic.cefr_level if w.grammar_topic else None)
            or profile.current_cefr_level
            or "A2"
        )
        batch = _build_and_save_batch(
            skill=w.skill,
            topic=w.grammar_topic,
            cefr_level=cefr,
            difficulty=target_difficulty,
            count=count_per_weakness,
            user=user,
            seen_questions=seen_questions,
        )
        saved.extend(batch)

    _notify_exercises_generated(user, saved, target_difficulty)
    return saved


def _notify_exercises_generated(user, saved, difficulty: float) -> None:
    if not saved:
        return
    try:
        from notifications import constants as C
        from notifications.services import NotificationService
        NotificationService().trigger(
            C.EXERCISES_GENERATED,
            user=user,
            payload={
                "count": len(saved),
                "cta_url": "/dashboard/",
                "cta_label": "Start now",
                "dedup_key": f"exgen:{len(saved)}:{int(difficulty * 100)}",
            },
        )
    except Exception as e:
        logger.warning("exercises_generated notify failed: %s", e)


def _build_and_save_batch(
    *,
    skill: Skill | None,
    topic: GrammarTopic | None,
    cefr_level: str,
    difficulty: float,
    count: int,
    user,
    seen_questions: set[str] | None = None,
) -> list[AdaptiveExercise]:
    seen_questions = seen_questions if seen_questions is not None else set()

    raw = (
        _call_ai(
            skill=skill.category if skill else "",
            topic=topic.name if topic else "",
            cefr_level=cefr_level,
            difficulty=difficulty,
            count=count,
        )
        if settings.AI_API_KEY
        else None
    )

    items: list[dict]
    generated_by_ai = False
    if raw is not None:
        items = _validate_ai_items(raw)
        generated_by_ai = bool(items)

    if not (raw is not None and generated_by_ai):
        logger.info(
            "Exercise generator: using fallback templates (skill=%s, topic=%s)",
            skill.category if skill else None,
            topic.name if topic else None,
        )
        items = exercise_templates.render_fallback(
            skill=skill,
            topic=topic,
            cefr_level=cefr_level,
            difficulty=difficulty,
            count=count,
        )

    saved: list[AdaptiveExercise] = []
    rows: list[AdaptiveExercise] = []
    for it in items:
        question = (it.get("question") or "").strip()
        if not question or question in seen_questions:
            continue
        seen_questions.add(question)
        rows.append(
            AdaptiveExercise(
                topic=topic,
                skill=skill,
                cefr_level=it.get("cefr_level") or cefr_level,
                difficulty_score=_clamp_difficulty(it.get("difficulty_score", difficulty)),
                question_type=it["question_type"],
                question=question,
                options=it.get("options") or [],
                correct_answer=it.get("correct_answer", ""),
                explanation=it.get("explanation", ""),
                generated_by_ai=generated_by_ai,
                metadata={
                    "model": settings.AI_MODEL if generated_by_ai else "fallback",
                    "prompt_version": PROMPT_VERSION,
                    "source": "ai" if generated_by_ai else "template",
                    "user_id": getattr(user, "id", None),
                },
            )
        )
        if len(rows) >= count:
            break

    if rows:
        with transaction.atomic():
            saved = AdaptiveExercise.objects.bulk_create(rows)
    return saved


def _clamp_difficulty(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = 0.5
    return max(0.0, min(1.0, f))


def _call_ai(*, skill: str, topic: str, cefr_level: str, difficulty: float, count: int) -> dict | None:
    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": EXERCISE_GEN_SYSTEM},
            {
                "role": "user",
                "content": build_exercise_gen_user_prompt(
                    skill=skill,
                    grammar_topic=topic,
                    cefr_level=cefr_level,
                    difficulty=difficulty,
                    count=count,
                ),
            },
        ],
        "tools": [EXERCISE_GEN_TOOL],
        "tool_choice": {
            "type": "function",
            "function": {"name": "produce_exercises"},
        },
    }
    try:
        resp = requests.post(
            f"{settings.AI_API_BASE.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        tool_call = data["choices"][0]["message"]["tool_calls"][0]
        result = json.loads(tool_call["function"]["arguments"])
        try:
            from core.services.ai_usage import log_usage
            usage = data.get("usage", {}) or {}
            log_usage(
                None, "exercise_generation", model=settings.AI_MODEL,
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                success=True,
            )
        except Exception:
            pass
        return result
    except Exception as e:
        logger.warning("Exercise generator AI call failed: %s", e)
        try:
            from core.services.ai_usage import log_usage
            log_usage(None, "exercise_generation", model=settings.AI_MODEL, success=False, error_message=str(e))
        except Exception:
            pass
        return None


def _validate_ai_items(raw) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    items = raw.get("exercises")
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        qt = it.get("question_type")
        if qt not in ALLOWED_QUESTION_TYPES:
            continue
        if not it.get("question") or not it.get("correct_answer"):
            continue
        out.append(it)
    return out
