"""On-demand variation generator.

Different from `factory_generate`: this module does **not** persist anything.
It returns rendered question dicts for a topic / template / variant. Use
this when:
  * a lesson wants a "fresh" question without burning a DB row
  * an exam needs an item at a specific variant for replay
  * a tutor wants 1000 candidates to filter on the fly

The generator is deterministic — the same `(topic, variant)` pair always
returns the same item — which is what lets us advertise "unlimited
variations" without ever materialising 100 trillion rows."""
from __future__ import annotations

import random
from typing import Iterable

from django.db.models import QuerySet

from .template_engine import (
    deterministic_seed,
    maximum_variations,
    render_many,
    render_one,
)
from ..models import QuestionTemplate, Topic


def _select_templates(
    *,
    topic_slug: str | None = None,
    topic_kind: str | None = None,
    cefr_level: str | None = None,
    question_type: str | None = None,
) -> QuerySet[QuestionTemplate]:
    qs = QuestionTemplate.objects.filter(is_active=True).select_related("topic")
    if topic_slug:
        qs = qs.filter(topic__slug=topic_slug)
    if topic_kind:
        qs = qs.filter(topic__kind=topic_kind)
    if cefr_level:
        qs = qs.filter(cefr_level=cefr_level) | qs.filter(cefr_level="", topic__cefr_level=cefr_level)
    if question_type:
        qs = qs.filter(question_type=question_type)
    return qs.distinct()


def variations_for_topic(
    topic_slug: str, *, count: int, start_variant: int = 0,
) -> list[dict]:
    """Walk the templates under a topic, round-robin, until `count` items."""
    templates = list(_select_templates(topic_slug=topic_slug))
    if not templates:
        return []
    out: list[dict] = []
    variant = start_variant
    while len(out) < count:
        progressed = False
        for tpl in templates:
            if len(out) >= count:
                break
            try:
                out.append(render_one(tpl, variant=variant))
                progressed = True
            except Exception:
                continue
        variant += 1
        if not progressed:
            break
    return out[:count]


def variations_for_topic_kind(
    topic_kind: str, *, cefr_level: str | None = None, count: int,
    seed: int = 0,
) -> list[dict]:
    """Spread `count` items across all active templates of a kind/level.
    Templates are picked uniformly with a stable seeded shuffle."""
    templates = list(_select_templates(topic_kind=topic_kind, cefr_level=cefr_level))
    if not templates:
        return []
    rng = random.Random(deterministic_seed("variations", seed))
    rng.shuffle(templates)
    out: list[dict] = []
    variant = 0
    while len(out) < count:
        progressed = False
        for tpl in templates:
            if len(out) >= count:
                break
            try:
                out.append(render_one(tpl, variant=variant))
                progressed = True
            except Exception:
                continue
        variant += 1
        if not progressed:
            break
    return out[:count]


def virtual_capacity(
    *, topic_slug: str | None = None, topic_kind: str | None = None,
    cefr_level: str | None = None,
) -> int:
    """Sum of max-variations across the matching templates.
    This is an *upper bound* on how many unique items the system can
    generate without ever persisting a single new row."""
    total = 0
    for tpl in _select_templates(
        topic_slug=topic_slug, topic_kind=topic_kind, cefr_level=cefr_level,
    ):
        total += maximum_variations(tpl)
    return total
