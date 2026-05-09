"""Hybrid generation: template renders the body, AI improves the
explanation and (optionally) generates better distractors.

Why this is useful:
- Template gives us deterministic, grammatical sentences for free.
- LLMs are better at writing pedagogical explanations than rule-based
  fallbacks (`"The correct answer is 'X'."`).
- Hybrid keeps AI cost bounded — at most one short call per item, only
  for the explanation, instead of generating the whole question.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from factory.services import llm_router

from . import duplicate_detector, question_validator, template_generator
from .. import constants as C
from ..models import GeneratedQuestion, GenerationBatch, QuestionBlueprint

logger = logging.getLogger(__name__)


def _improve_explanation(item: dict) -> str | None:
    """Ask the LLM router for a richer explanation. Returns None on failure
    so callers fall back to the template's explanation."""
    sys = (
        "You write concise, friendly ESL explanations. Reply with a single "
        "JSON object: {\"explanation\": \"<2-3 short sentences>\"}."
    )
    user = (
        f"CEFR level: {item.get('cefr_level')}\n"
        f"Skill: {item.get('skill')}\n"
        f"Question: {item.get('question_text')}\n"
        f"Correct answer: {item.get('correct_answer')}\n"
        "Explain why the answer is correct."
    )
    payload = llm_router.chat(
        [{"role": "system", "content": sys}, {"role": "user", "content": user}],
        json_mode=True,
    )
    parsed = llm_router.parse_json_content(payload)
    if not parsed:
        return None
    text = (parsed.get("explanation") or "").strip()
    return text or None


def generate_for_blueprint(
    blueprint: QuestionBlueprint, *,
    count: int,
    start_variant: int = 0,
    quality_threshold: int = 60,
    batch: GenerationBatch | None = None,
) -> dict:
    """Render N items with templates, then enrich each explanation via AI."""
    candidates = template_generator.render_for_blueprint(
        blueprint, count=count, start_variant=start_variant,
    )

    enriched, ai_used = [], 0
    for it in candidates:
        # Override generated_by tag and try to upgrade the explanation.
        it["generated_by"] = C.GEN_HYBRID
        new_expl = _improve_explanation(it)
        if new_expl:
            it["explanation"] = new_expl
            ai_used += 1
            it.setdefault("metadata", {})["explanation_source"] = "ai"
        # Re-stamp a hybrid-coded id so downstream stats track it correctly.
        it["code"] = f"qf:hyb:{blueprint.code}:{start_variant + len(enriched)}:{uuid.uuid4().hex[:6]}"
        enriched.append(it)

    accepted, rejected = [], 0
    for it in enriched:
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

    instances = [template_generator._to_model(it) for it in deduped]
    written = 0
    if instances:
        GeneratedQuestion.objects.bulk_create(
            instances, batch_size=300, ignore_conflicts=True,
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
        "ai_used":    ai_used,
    }
