"""AI extractors for chapter content.

Public:
    extract_chapter_lessons(chapter) -> dict
        Generates VocabularyExtract, GrammarExtract, and
        ComprehensionQuestion rows for a chapter.

Falls back to a deterministic rule-based extractor when AI is not configured.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

import requests
from django.conf import settings
from django.db import transaction

from library.models import (
    Chapter,
    ComprehensionQuestion,
    GrammarExtract,
    VocabularyExtract,
)

logger = logging.getLogger(__name__)

EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_chapter",
        "description": "Pull vocabulary, grammar focus, and comprehension Qs.",
        "parameters": {
            "type": "object",
            "properties": {
                "vocabulary": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "term": {"type": "string"},
                            "translation": {"type": "string"},
                            "pos": {"type": "string"},
                            "example": {"type": "string"},
                            "cefr_level": {"type": "string"},
                        },
                        "required": ["term"],
                        "additionalProperties": False,
                    },
                },
                "grammar": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string"},
                            "explanation": {"type": "string"},
                            "example": {"type": "string"},
                            "cefr_level": {"type": "string"},
                        },
                        "required": ["topic"],
                        "additionalProperties": False,
                    },
                },
                "comprehension": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "correct_answer": {"type": "string"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["question", "correct_answer"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["vocabulary", "grammar", "comprehension"],
            "additionalProperties": False,
        },
    },
}


def _build_prompt(chapter: Chapter) -> tuple[str, str]:
    sys = (
        "You are an English curriculum designer. Given a chapter of text, "
        "extract: (1) up to 8 useful vocabulary items with translations into "
        "Arabic; (2) up to 4 grammar focus topics; (3) up to 5 comprehension "
        "questions with short answers. Be concise and faithful to the text."
    )
    user = (
        f"Book: {chapter.book.title}\n"
        f"CEFR level: {chapter.book.level}\n"
        f"Chapter: {chapter.title}\n"
        f"---\n{chapter.body[:8000]}\n---\n"
        "Call extract_chapter with your structured output."
    )
    return sys, user


def _heuristic_extract(chapter: Chapter) -> dict:
    """Deterministic minimal extractor used when AI is not configured."""
    words = [w.strip(".,!?\"'()[]") for w in chapter.body.split()]
    long_words = sorted({w for w in words if len(w) >= 7})[:5]
    return {
        "vocabulary": [
            {"term": w, "translation": "", "pos": "", "example": "", "cefr_level": chapter.book.level}
            for w in long_words
        ],
        "grammar": [
            {
                "topic": "Reading comprehension",
                "explanation": "Identify subject, verb, and object in the chapter's sentences.",
                "example": "",
                "cefr_level": chapter.book.level,
            }
        ],
        "comprehension": [
            {
                "question": f"What is the main idea of '{chapter.title}'?",
                "options": [],
                "correct_answer": "",
                "explanation": "Open-ended.",
            }
        ],
    }


def _call_ai(chapter: Chapter) -> dict | None:
    sys, user = _build_prompt(chapter)
    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        "tools": [EXTRACT_TOOL],
        "tool_choice": {
            "type": "function",
            "function": {"name": "extract_chapter"},
        },
    }
    try:
        # Centralised ai_usage wrapper (Prompt 12A.1): library content
        # extraction, role=system. Function-calling via extra_payload.
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        data = ai_client.chat(
            payload["messages"], feature=AC.FEATURE_CONTENT_GENERATION,
            role=AC.ROLE_SYSTEM, model=settings.AI_MODEL,
            extra_payload={"tools": payload["tools"],
                           "tool_choice": payload["tool_choice"]},
            timeout=60,
        )
        tool_call = data["choices"][0]["message"]["tool_calls"][0]
        result = json.loads(tool_call["function"]["arguments"])
        return result
    except Exception as e:
        logger.warning("Library extractor AI call failed: %s", e)
        return None


@transaction.atomic
def extract_chapter_lessons(chapter: Chapter) -> dict:
    """Run extractors for a chapter and persist results. Returns counts."""
    raw = _call_ai(chapter) if settings.AI_API_KEY else None
    if raw is None or not isinstance(raw, dict):
        raw = _heuristic_extract(chapter)

    vocab_rows: list[VocabularyExtract] = []
    for v in raw.get("vocabulary", []) or []:
        term = (v.get("term") or "").strip()
        if not term:
            continue
        vocab_rows.append(
            VocabularyExtract(
                chapter=chapter,
                term=term[:120],
                translation=(v.get("translation") or "")[:200],
                pos=(v.get("pos") or "")[:20],
                example=(v.get("example") or "")[:1000],
                cefr_level=(v.get("cefr_level") or chapter.book.level)[:2],
            )
        )

    grammar_rows: list[GrammarExtract] = []
    for g in raw.get("grammar", []) or []:
        topic = (g.get("topic") or "").strip()
        if not topic:
            continue
        grammar_rows.append(
            GrammarExtract(
                chapter=chapter,
                topic=topic[:120],
                explanation=(g.get("explanation") or "")[:1500],
                example=(g.get("example") or "")[:500],
                cefr_level=(g.get("cefr_level") or chapter.book.level)[:2],
            )
        )

    comp_rows: list[ComprehensionQuestion] = []
    for i, q in enumerate(raw.get("comprehension", []) or []):
        question = (q.get("question") or "").strip()
        correct = (q.get("correct_answer") or "").strip()
        if not question:
            continue
        comp_rows.append(
            ComprehensionQuestion(
                chapter=chapter,
                question=question[:1000],
                options=q.get("options") or [],
                correct_answer=correct[:500],
                explanation=(q.get("explanation") or "")[:1000],
                sort_order=i,
            )
        )

    # Replace existing extractions for this chapter to keep things idempotent.
    VocabularyExtract.objects.filter(chapter=chapter).delete()
    GrammarExtract.objects.filter(chapter=chapter).delete()
    ComprehensionQuestion.objects.filter(chapter=chapter).delete()

    if vocab_rows:
        VocabularyExtract.objects.bulk_create(vocab_rows, ignore_conflicts=True)
    if grammar_rows:
        GrammarExtract.objects.bulk_create(grammar_rows)
    if comp_rows:
        ComprehensionQuestion.objects.bulk_create(comp_rows)

    return {
        "vocabulary": len(vocab_rows),
        "grammar": len(grammar_rows),
        "comprehension": len(comp_rows),
    }
