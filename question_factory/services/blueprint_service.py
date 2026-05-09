"""CRUD + lookup helpers for QuestionBlueprint.

Most call sites want to filter blueprints by (cefr_level, skill,
question_type, strategy) — so this module bundles those into one API
rather than having every caller compose its own queryset."""
from __future__ import annotations

from typing import Iterable, Optional

from django.db.models import QuerySet

from .. import constants as C
from ..models import QuestionBlueprint


def filter_blueprints(
    *,
    cefr_level: str | None = None,
    skill: str | None = None,
    question_type: str | None = None,
    strategy: str | None = None,
    grammar_topic_id: int | None = None,
    is_active: bool | None = True,
) -> QuerySet[QuestionBlueprint]:
    qs = QuestionBlueprint.objects.all()
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if cefr_level:
        qs = qs.filter(cefr_level=cefr_level)
    if skill:
        qs = qs.filter(skill=skill)
    if question_type:
        qs = qs.filter(question_type=question_type)
    if strategy:
        qs = qs.filter(generation_strategy=strategy)
    if grammar_topic_id:
        qs = qs.filter(grammar_topic_id=grammar_topic_id)
    return qs


def get_by_code(code: str) -> Optional[QuestionBlueprint]:
    return QuestionBlueprint.objects.filter(code=code).first()


def by_signature(*, cefr_level: str, skill: str, question_type: str
                 ) -> QuestionBlueprint | None:
    """Lookup the canonical blueprint for a (level, skill, type) tuple."""
    return filter_blueprints(
        cefr_level=cefr_level, skill=skill, question_type=question_type,
    ).first()


def upsert(*, code: str, **defaults) -> QuestionBlueprint:
    """Idempotent create-or-update keyed by `code`. Used by seed scripts."""
    obj, _ = QuestionBlueprint.objects.update_or_create(
        code=code, defaults=defaults,
    )
    return obj


def stats() -> dict:
    """Bank-wide stats for dashboards. Aggregated in DB."""
    from django.db.models import Count
    qs = QuestionBlueprint.objects.filter(is_active=True)
    out = {"total": qs.count(),
           "by_cefr": {}, "by_skill": {}, "by_strategy": {}, "by_qtype": {}}
    for k, v in qs.values_list("cefr_level").annotate(c=Count("id")):
        out["by_cefr"][k or ""] = v
    for k, v in qs.values_list("skill").annotate(c=Count("id")):
        out["by_skill"][k or ""] = v
    for k, v in qs.values_list("generation_strategy").annotate(c=Count("id")):
        out["by_strategy"][k or ""] = v
    for k, v in qs.values_list("question_type").annotate(c=Count("id")):
        out["by_qtype"][k or ""] = v
    return out
