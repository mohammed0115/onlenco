"""Score a model's output against the test split of a `DatasetBuild`.

For each task type we have a different scorer:
  * `cefr_prediction` / `error_analysis`  — exact label match (accuracy)
  * `difficulty_estimation`               — MAE on float
  * `exercise_generation` / `answer_explanation` / `tutor_reply`
                                          — character-overlap proxy
                                            (real eval needs human / BLEU /
                                             a reward model — for now this
                                             at least catches the "model
                                             returned nothing" case).

The evaluator deliberately calls the model router rather than a specific
provider so that eval scoring picks up whatever provider the router
would actually serve in production. Pass `forced_provider` to lock to
one provider for A/B-style comparisons.
"""
from __future__ import annotations

import logging
import time
from typing import Iterable

from django.utils import timezone

from ai_engine.services import providers as ai_providers
from ai_engine.services.model_router import route_task

from .. import constants as C
from ..models import (
    AITrainingExample, DatasetBuild, EvaluationRun,
)

logger = logging.getLogger(__name__)


def _label_score(pred: dict, gold: dict, *, key: str) -> bool:
    p = (pred or {}).get(key)
    g = (gold or {}).get(key)
    if p is None or g is None:
        return False
    return str(p).strip().lower() == str(g).strip().lower()


def _difficulty_score(pred: dict, gold: dict) -> float | None:
    """Return the absolute error for one prediction, or None if unscoreable."""
    try:
        p = float((pred or {}).get("label"))
        g = float((gold or {}).get("label"))
    except (TypeError, ValueError):
        return None
    return abs(p - g)


def _text_overlap(pred: dict, gold: dict, *, key: str) -> float:
    """0..1 token-overlap proxy for free-form generation."""
    p = str((pred or {}).get(key) or "").strip().lower()
    g = str((gold or {}).get(key) or "").strip().lower()
    if not p or not g:
        return 0.0
    pset = {t for t in p.split() if len(t) > 1}
    gset = {t for t in g.split() if len(t) > 1}
    if not pset or not gset:
        return 0.0
    return len(pset & gset) / len(pset | gset)


def _build_router_input(task_type: str, gold_input: dict) -> dict:
    """Map an AITrainingExample.input into the shape the router expects."""
    if task_type == C.TASK_CEFR_PREDICTION:
        return {"text": gold_input.get("text") or ""}
    if task_type == C.TASK_ERROR_ANALYSIS:
        return {
            "question": gold_input.get("question") or "",
            "student_answer": gold_input.get("student_answer") or "",
            "correct_answer": gold_input.get("correct_answer") or "",
        }
    if task_type == C.TASK_EXERCISE_GENERATION:
        return {
            "cefr_level": gold_input.get("cefr_level") or "",
            "skill": gold_input.get("skill") or "",
            "topic": gold_input.get("topic") or "",
            "difficulty": gold_input.get("difficulty"),
            "question_type": gold_input.get("question_type") or "",
        }
    if task_type == C.TASK_ANSWER_EXPLANATION:
        return {
            "question": gold_input.get("question") or "",
            "student_answer": gold_input.get("student_answer") or "",
            "correct_answer": gold_input.get("correct_answer") or "",
        }
    if task_type == C.TASK_TUTOR_REPLY:
        return {
            "student_question": (gold_input.get("student_question")
                                  or gold_input.get("question") or ""),
            "context": gold_input.get("context") or {},
        }
    return dict(gold_input)


def _score_one(task_type: str, predicted_output: dict, gold_output: dict
               ) -> tuple[bool, float | None]:
    """Return (correct, abs_error). `abs_error` is filled only for regression."""
    if task_type == C.TASK_CEFR_PREDICTION:
        return _label_score(predicted_output, gold_output, key="cefr_level"), None

    if task_type == C.TASK_ERROR_ANALYSIS:
        return _label_score(predicted_output, gold_output, key="error_type"), None

    if task_type == "difficulty_estimation":  # not in C.TASK_TYPE_CHOICES
        err = _difficulty_score(predicted_output, gold_output)
        if err is None:
            return False, None
        return err <= 0.15, err   # arbitrary "within 0.15" threshold

    if task_type in (C.TASK_EXERCISE_GENERATION,
                     C.TASK_ANSWER_EXPLANATION,
                     C.TASK_TUTOR_REPLY):
        key = {
            C.TASK_EXERCISE_GENERATION: "question",
            C.TASK_ANSWER_EXPLANATION:  "explanation",
            C.TASK_TUTOR_REPLY:         "reply",
        }[task_type]
        score = _text_overlap(predicted_output, gold_output, key=key)
        return score >= 0.30, None  # crude threshold

    return False, None


def evaluate_build(
    build: DatasetBuild,
    *,
    name: str,
    forced_provider: str | None = None,
    limit: int = 0,
) -> EvaluationRun:
    """Run the test split of `build` through the router and score it.

    `forced_provider` swaps the entire `PROVIDERS` registry to use only
    that provider — useful for A/B comparisons (e.g. "if I disable
    OpenAI, how does my local stack perform?")."""
    run = EvaluationRun.objects.create(
        name=name, build=build, task_type=build.task_type,
        provider=forced_provider or "", status=C.BUILD_RUNNING,
    )

    qs = AITrainingExample.objects.filter(
        task_type=build.task_type,
        metadata__build_id=build.id,
        split=C.SPLIT_TEST,
    )
    if limit:
        qs = qs[:limit]

    rows = list(qs)
    if not rows:
        run.status = C.BUILD_FAILED
        run.error_message = "No test examples for this build."
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_message", "completed_at"])
        return run

    correct = incorrect = skipped = 0
    abs_errors: list[float] = []
    latencies: list[int] = []
    providers_used: dict[str, int] = {}

    # Optionally restrict the provider pool.
    original_providers = None
    if forced_provider:
        original_providers = dict(ai_providers.PROVIDERS)
        ai_providers.PROVIDERS.clear()
        if forced_provider in original_providers:
            ai_providers.PROVIDERS[forced_provider] = original_providers[forced_provider]

    try:
        for row in rows:
            t0 = time.time()
            try:
                result = route_task(
                    build.task_type,
                    _build_router_input(build.task_type, row.input or {}),
                )
            except Exception as e:
                logger.warning("eval: route_task crashed: %s", e)
                skipped += 1
                continue
            latencies.append(int((time.time() - t0) * 1000))
            providers_used[result["provider"]] = providers_used.get(result["provider"], 0) + 1
            if result["provider"] == "none":
                skipped += 1
                continue
            ok, err = _score_one(build.task_type, result["output"], row.output or {})
            if err is not None:
                abs_errors.append(err)
            if ok:
                correct += 1
            else:
                incorrect += 1
    finally:
        if original_providers is not None:
            ai_providers.PROVIDERS.clear()
            ai_providers.PROVIDERS.update(original_providers)

    total = correct + incorrect + skipped
    run.total_examples = total
    run.correct_count  = correct
    run.incorrect_count = incorrect
    run.skipped_count  = skipped
    run.accuracy = (correct / max(1, correct + incorrect)) if (correct + incorrect) else 0.0
    if abs_errors:
        run.mean_absolute_error = sum(abs_errors) / len(abs_errors)
    if latencies:
        run.avg_latency_ms = int(sum(latencies) / len(latencies))
    run.metadata = {"providers_used": providers_used}
    run.status = C.BUILD_COMPLETED
    run.completed_at = timezone.now()
    run.save(update_fields=[
        "total_examples", "correct_count", "incorrect_count",
        "skipped_count", "accuracy", "mean_absolute_error",
        "avg_latency_ms", "metadata", "status", "completed_at",
    ])
    return run
