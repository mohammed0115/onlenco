"""Main RAG entry point.

`retrieve_examples()` is the single function call sites should reach
for. It dispatches to:

  * `question_retriever.retrieve_questions(...)` for exercise_generation
    (you want real questions to imitate)
  * `example_retriever.retrieve_examples(...)` for everything else
    (you want curated (input, output) pairs from AITrainingExample)

Two-tier fallback: when the curated training corpus is empty for a
task, the retriever falls back to the raw source — so the day-1
deployment, before any training examples are built, still gets
something useful from the live question bank.
"""
from __future__ import annotations

import logging
from typing import Any

from . import context_builder, example_retriever, question_retriever

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task-type dispatch
# ---------------------------------------------------------------------------

def _retrieve_for_exercise_generation(
    *, cefr_level, skill, topic, difficulty, question_type, query, limit,
) -> list[dict]:
    """Pull real reference questions from the live bank."""
    items = question_retriever.retrieve_questions(
        cefr_level=cefr_level, skill=skill,
        grammar_topic=topic, vocabulary_topic=topic,
        difficulty=difficulty, question_type=question_type,
        query=query, limit=limit,
    )
    return items


def _retrieve_for_curated_task(
    task_type: str, *, cefr_level, skill, query, limit,
) -> list[dict]:
    """Pull curated (input, output) pairs from AITrainingExample."""
    return example_retriever.retrieve_examples(
        task_type=task_type,
        cefr_level=cefr_level, skill=skill,
        query=query, limit=limit,
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def retrieve_examples(
    task_type: str,
    cefr_level: str | None = None,
    skill: str | None = None,
    topic: str | None = None,
    difficulty: float | None = None,
    *,
    question_type: str | None = None,
    query: str | None = None,
    weaknesses: list[dict] | None = None,
    limit: int = 5,
) -> dict:
    """Retrieve relevant examples + build the prompt context.

    Returns a dict:
      {
        "task_type": "...",
        "items":     [...],           # raw retrieved items
        "context":   {...},           # LLM-ready prompt context
        "source":    "questions" | "training_examples" | "fallback" | "none",
        "count":     N,
      }
    """
    if task_type == "exercise_generation":
        items = _retrieve_for_exercise_generation(
            cefr_level=cefr_level, skill=skill, topic=topic,
            difficulty=difficulty, question_type=question_type,
            query=query, limit=limit,
        )
        source = "questions"
    else:
        items = _retrieve_for_curated_task(
            task_type=task_type, cefr_level=cefr_level,
            skill=skill, query=query, limit=limit,
        )
        source = "training_examples"

        # Fallback: when no curated training examples exist, derive a
        # weaker context from real questions (cheap RAG day-1).
        if not items and task_type in {"answer_explanation", "tutor_reply"}:
            fallback = question_retriever.retrieve_questions(
                cefr_level=cefr_level, skill=skill,
                grammar_topic=topic, vocabulary_topic=topic,
                difficulty=difficulty, query=query, limit=limit,
            )
            if fallback:
                items = [
                    {
                        "task_type": task_type,
                        "input": {
                            "question": q["question"],
                            "correct_answer": q["correct_answer"],
                        },
                        "output": {"explanation": q["explanation"]},
                        "cefr_level": q["cefr_level"],
                        "skill": q["skill"],
                        "quality_score": q["quality_score"],
                        "source": "fallback_from_question_bank",
                    }
                    for q in fallback
                ]
                source = "fallback"

    if not items:
        return {
            "task_type": task_type, "items": [], "context": {},
            "source": "none", "count": 0,
        }

    context = context_builder.build_for_task(
        task_type, items=items, weaknesses=weaknesses, limit=limit,
    )
    return {
        "task_type": task_type, "items": items, "context": context,
        "source": source, "count": len(items),
    }


# ---------------------------------------------------------------------------
# Convenience wrappers — let call sites avoid the dispatch dict
# ---------------------------------------------------------------------------

def retrieve_questions(*args, **kwargs) -> list[dict]:
    """Pass-through to `question_retriever.retrieve_questions` with the
    same kwargs. Provided so call sites can use a single import."""
    return question_retriever.retrieve_questions(*args, **kwargs)


def retrieve_training_examples(*args, **kwargs) -> list[dict]:
    """Pass-through to `example_retriever.retrieve_examples`."""
    return example_retriever.retrieve_examples(*args, **kwargs)
