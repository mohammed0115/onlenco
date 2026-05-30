"""Pick + order the questions for a Challenge Session.

Phase 1 scope (no adaptive logic):
  * Reads the existing `LessonQuiz.questions` queryset.
  * Drops question_types the grader doesn't yet support — logs a
    warning instead of crashing the session.
  * Preserves the author-defined `order` field.
  * Caps the session at `MAX_CARDS` to keep a Challenge under ~3 min.

Hooks for later phases:
  * `_select_supported(...)` is where adaptive prioritisation will plug
    in once `learning_core` is wired (Phase 5).
"""
from __future__ import annotations

import logging
from typing import Iterable

from courses.models import LessonQuestion, LessonQuiz
from courses.services import question_type_registry as registry


logger = logging.getLogger(__name__)

# Back-compat alias — the original Phase 1 set was hard-coded here.
# Other code may import this; we re-derive from the registry now so
# adding a new type only needs one edit.
SUPPORTED_QUESTION_TYPES: set[str] = {
    code for code, spec in registry.ALL_TYPES.items()
    if spec.get("supports_challenge")
}

MAX_CARDS = 12   # spec: 6–12 per Challenge


def compose_question_ids(quiz: LessonQuiz) -> list[int]:
    """Return the ordered list of question ids that will be played.

    Filters by supported types and trims to MAX_CARDS. Skipped types
    are logged once per quiz so the operator can see which questions
    didn't enter the rotation.
    """
    all_questions = list(
        quiz.questions.all().order_by("order", "id")
    )
    selected, skipped = _select_supported(all_questions)

    if skipped:
        logger.info(
            "Challenge composer for quiz %s skipped %d question(s) of "
            "unsupported types: %s",
            quiz.pk, len(skipped),
            sorted({q.question_type for q in skipped}),
        )

    return [q.id for q in selected[:MAX_CARDS]]


def _select_supported(
    questions: Iterable[LessonQuestion],
) -> tuple[list[LessonQuestion], list[LessonQuestion]]:
    """Split into (selected, skipped). Plug point for adaptive sort."""
    selected: list[LessonQuestion] = []
    skipped:  list[LessonQuestion] = []
    for q in questions:
        if q.question_type in SUPPORTED_QUESTION_TYPES:
            selected.append(q)
        else:
            skipped.append(q)
    # TODO (Phase 5): re-order `selected` by mastery-EMA weakness.
    return selected, skipped
