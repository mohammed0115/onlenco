"""Retrieve real questions from the curated bank.

Sources (in order of preference):
  1. `learning_core.AdaptiveExercise` — production bank, the most
     reliable corpus. Only `is_active=True, is_reviewed=True` rows
     are eligible.
  2. `question_factory.GeneratedQuestion` — staging items that have
     been explicitly `approved_for_training=True`.

Ranking
-------
- Filters narrow the candidate set first (CEFR, skill, topic, type).
- When more candidates remain than `limit`, we score them:
    * keyword_overlap(query, question_text)        — primary
    * 1.0 − abs(question.difficulty − target)      — proximity
    * quality_score / 100                          — quality bump
  and return the top `limit`.

Embeddings
----------
`AI_EMBEDDING_PROVIDER` setting may opt the system into
embedding-based ranking later. The hook is in `_embedding_score()` —
returns 0.0 today, so the keyword path always wins.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

from django.conf import settings
from django.db.models import F, Q

from learning_core.models import AdaptiveExercise
from question_factory.models import GeneratedQuestion

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


# ---------------------------------------------------------------------------
# Tokeniser + scoring
# ---------------------------------------------------------------------------

def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1}


def _keyword_overlap(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    cand_tokens = _tokens(text)
    if not cand_tokens:
        return 0.0
    return len(query_tokens & cand_tokens) / len(query_tokens)


def _difficulty_proximity(target: float | None, candidate: float | None) -> float:
    if target is None or candidate is None:
        return 0.0
    return max(0.0, 1.0 - abs(float(target) - float(candidate)))


def _embedding_score(query: str, candidate: str) -> float:
    """Hook for embedding-based ranking. Returns 0.0 unless an
    embeddings provider is configured (none by default)."""
    if not getattr(settings, "AI_EMBEDDING_PROVIDER", ""):
        return 0.0
    return 0.0  # TODO: wire pgvector / sentence-transformers


def _score_candidate(*, query_tokens: set[str], target_difficulty: float | None,
                     question_text: str, candidate_difficulty: float | None,
                     quality_score: int) -> float:
    return (
        2.0  * _keyword_overlap(query_tokens, question_text)
        + 1.0 * _difficulty_proximity(target_difficulty, candidate_difficulty)
        + 0.5 * (max(0, quality_score) / 100.0)
        + 1.0 * _embedding_score(" ".join(query_tokens), question_text)
    )


# ---------------------------------------------------------------------------
# Adapters — surface the two question stores under a uniform dict shape
# ---------------------------------------------------------------------------

def _serialise_adaptive(ex: AdaptiveExercise) -> dict:
    topic = ex.topic.name if ex.topic_id and ex.topic else ""
    skill = ex.skill.category if ex.skill_id and ex.skill else ""
    return {
        "source": "AdaptiveExercise",
        "id": ex.id,
        "code": ex.code or "",
        "question": ex.question,
        "options": list(ex.options or []),
        "correct_answer": ex.correct_answer,
        "explanation": ex.explanation or "",
        "cefr_level": ex.cefr_level or "",
        "skill": skill,
        "grammar_topic": topic,
        "difficulty": float(ex.difficulty_score or 0.5),
        "quality_score": int(ex.quality_score or 0),
        "question_type": ex.question_type,
        "language": ex.language or "en",
    }


def _serialise_generated(gq: GeneratedQuestion) -> dict:
    return {
        "source": "GeneratedQuestion",
        "id": gq.id,
        "code": gq.code or "",
        "question": gq.question_text,
        "options": list(gq.options or []),
        "correct_answer": gq.correct_answer,
        "explanation": gq.explanation or "",
        "cefr_level": gq.cefr_level or "",
        "skill": gq.skill or "",
        "grammar_topic": (
            gq.grammar_topic.name if gq.grammar_topic_id and gq.grammar_topic else ""
        ),
        "vocabulary_topic": gq.vocabulary_topic or "",
        "difficulty": float(gq.difficulty_score or 0.5),
        "quality_score": int(gq.quality_score or 0),
        "question_type": gq.question_type,
        "language": "en",
    }


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def _adaptive_qs(*, cefr_level, skill, grammar_topic, difficulty,
                 question_type, query):
    qs = AdaptiveExercise.objects.filter(is_active=True, is_reviewed=True)
    if cefr_level:
        qs = qs.filter(cefr_level=cefr_level)
    if skill:
        qs = qs.filter(skill__category=skill)
    if grammar_topic:
        qs = qs.filter(
            Q(topic__slug=grammar_topic) | Q(topic__name__iexact=grammar_topic)
        )
    if question_type:
        qs = qs.filter(question_type=question_type)
    if query:
        qs = qs.filter(
            Q(question__icontains=query) | Q(explanation__icontains=query),
        )
    return qs.select_related("skill", "topic")


def _generated_qs(*, cefr_level, skill, grammar_topic, vocabulary_topic,
                  difficulty, question_type, query):
    qs = GeneratedQuestion.objects.filter(
        is_active=True, is_reviewed=True, approved_for_training=True,
    )
    if cefr_level:
        qs = qs.filter(cefr_level=cefr_level)
    if skill:
        qs = qs.filter(skill=skill)
    if grammar_topic:
        qs = qs.filter(
            Q(grammar_topic__slug=grammar_topic)
            | Q(grammar_topic__name__iexact=grammar_topic),
        )
    if vocabulary_topic:
        qs = qs.filter(vocabulary_topic__iexact=vocabulary_topic)
    if question_type:
        qs = qs.filter(question_type=question_type)
    if query:
        qs = qs.filter(
            Q(question_text__icontains=query) | Q(explanation__icontains=query),
        )
    return qs.select_related("grammar_topic")


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

DEFAULT_CANDIDATE_POOL = 50  # how many rows to consider before re-ranking


def retrieve_questions(
    *,
    cefr_level: str | None = None,
    skill: str | None = None,
    grammar_topic: str | None = None,
    vocabulary_topic: str | None = None,
    difficulty: float | None = None,
    question_type: str | None = None,
    query: str | None = None,
    limit: int = 5,
    include_generated: bool = True,
    candidate_pool: int = DEFAULT_CANDIDATE_POOL,
) -> list[dict]:
    """Return up to `limit` questions matching the filters, ranked by
    keyword + proximity + quality. Always returns active+reviewed rows."""
    candidates: list[dict] = []

    # Tier 1: production bank.
    adaptive_qs = _adaptive_qs(
        cefr_level=cefr_level, skill=skill,
        grammar_topic=grammar_topic, difficulty=difficulty,
        question_type=question_type, query=query,
    )[:candidate_pool]
    for ex in adaptive_qs:
        candidates.append(_serialise_adaptive(ex))

    # Tier 2: approved staging items, but only when we still need more.
    if include_generated and len(candidates) < candidate_pool:
        room = candidate_pool - len(candidates)
        generated_qs = _generated_qs(
            cefr_level=cefr_level, skill=skill,
            grammar_topic=grammar_topic, vocabulary_topic=vocabulary_topic,
            difficulty=difficulty, question_type=question_type, query=query,
        )[:room]
        for gq in generated_qs:
            candidates.append(_serialise_generated(gq))

    # Dedup by (question, correct_answer) tuple.
    seen, deduped = set(), []
    for c in candidates:
        key = (c["question"].strip().lower(), c["correct_answer"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    # Re-rank.
    qtokens = _tokens(query or "")
    for c in deduped:
        c["_score"] = _score_candidate(
            query_tokens=qtokens, target_difficulty=difficulty,
            question_text=c["question"],
            candidate_difficulty=c["difficulty"],
            quality_score=c["quality_score"],
        )
    deduped.sort(key=lambda c: c["_score"], reverse=True)
    for c in deduped:
        c.pop("_score", None)
    return deduped[:limit]
