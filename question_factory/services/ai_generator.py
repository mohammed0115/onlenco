"""AI-only generator: blueprint → LLM → GeneratedQuestion.

Uses the existing local-first router (`factory.services.llm_router`) so:
  * a configured local LLM endpoint is preferred,
  * OpenAI is the *fallback*, not the default.

This module owns prompt construction + JSON parsing + persistence. It
shares dedup/validation/persistence with the template generator so AI-
generated items go through the same quality gate."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from django.utils import timezone

from factory.services import llm_router

from . import duplicate_detector, question_validator
from .template_generator import _to_model
from .. import constants as C
from ..models import GeneratedQuestion, GenerationBatch, QuestionBlueprint

logger = logging.getLogger(__name__)


def _build_messages(blueprint: QuestionBlueprint, count: int) -> list[dict]:
    sys = (
        "You are an ESL question author. Generate questions for the Onlenco "
        "platform. Match the CEFR level exactly. Avoid offensive content, "
        "raw technical tokens, and duplicate questions. Output strict JSON only."
    )
    user = (
        f"Generate {count} questions following this blueprint.\n"
        f"Blueprint code: {blueprint.code}\n"
        f"CEFR level: {blueprint.cefr_level}\n"
        f"Skill: {blueprint.skill}\n"
        f"Question type: {blueprint.question_type}\n"
        f"Title: {blueprint.title}\n"
        f"Pattern hint: {blueprint.template_pattern}\n"
        f"Difficulty: {blueprint.difficulty_min}–{blueprint.difficulty_max}\n\n"
        'Return JSON: {"questions": [{"question_text": "...", "options": [...], '
        '"correct_answer": "...", "acceptable_answers": [...], '
        '"explanation": "...", "feedback_correct": "...", '
        '"feedback_wrong": "..."}]}'
    )
    return [
        {"role": "system", "content": sys},
        {"role": "user",   "content": user},
    ]


def _parse_response(blueprint: QuestionBlueprint, payload: dict | None
                    ) -> list[dict]:
    data = llm_router.parse_json_content(payload)
    if not data:
        return []
    out: list[dict] = []
    for i, raw in enumerate(data.get("questions") or []):
        if not isinstance(raw, dict):
            continue
        q = (raw.get("question_text") or "").strip()
        a = (raw.get("correct_answer") or "").strip()
        if not q or not a:
            continue
        opts = list(raw.get("options") or [])
        code = f"qf:ai:{blueprint.code}:{uuid.uuid4().hex[:8]}:{i}"
        item = {
            "code": code,
            "blueprint_id": blueprint.id,
            "blueprint_code": blueprint.code,
            "cefr_level": blueprint.cefr_level or "",
            "skill": blueprint.skill or "",
            "question_type": blueprint.question_type,
            "grammar_topic_id": blueprint.grammar_topic_id,
            "vocabulary_topic": blueprint.vocabulary_topic or "",
            "difficulty_score": (blueprint.difficulty_min + blueprint.difficulty_max) / 2.0,
            "question_text": q,
            "options": opts,
            "correct_answer": a,
            "acceptable_answers": list(raw.get("acceptable_answers") or [a]),
            "explanation": raw.get("explanation") or "",
            "feedback_correct": raw.get("feedback_correct") or "Correct!",
            "feedback_wrong": raw.get("feedback_wrong") or f"The correct answer is '{a}'.",
            "generated_by": C.GEN_AI,
            "content_hash": duplicate_detector.hash_question(q, a),
            "metadata": {
                "blueprint_code": blueprint.code,
                "served_by": (payload or {}).get("_router", {}).get("served_by"),
            },
        }
        out.append(item)
    return out


def generate_for_blueprint(
    blueprint: QuestionBlueprint, *,
    count: int = 5,
    quality_threshold: int = 60,
    batch: GenerationBatch | None = None,
) -> dict:
    payload = llm_router.chat(_build_messages(blueprint, count), json_mode=True)
    candidates = _parse_response(blueprint, payload)

    accepted, rejected = [], 0
    for it in candidates:
        question_validator.annotate(it)
        if question_validator.passes(it, threshold=quality_threshold):
            accepted.append(it)
        else:
            rejected += 1

    new_items, dup_count = duplicate_detector.bulk_filter_new(accepted)
    seen, deduped = set(), []
    for it in new_items:
        h = it["content_hash"]
        if h in seen:
            dup_count += 1
            continue
        seen.add(h)
        deduped.append(it)

    instances = [_to_model(it) for it in deduped]
    written = 0
    if instances:
        GeneratedQuestion.objects.bulk_create(
            instances, batch_size=200, ignore_conflicts=True,
        )
        written = len(instances)

    if batch is not None:
        batch.generated_count += len(candidates)
        batch.accepted_count  += written
        batch.rejected_count  += rejected
        batch.duplicate_count += dup_count
        batch.save(update_fields=[
            "generated_count", "accepted_count",
            "rejected_count", "duplicate_count",
        ])

    return {
        "candidates": len(candidates),
        "accepted":   written,
        "rejected":   rejected,
        "duplicates": dup_count,
        "served_by":  (payload or {}).get("_router", {}).get("served_by"),
    }
