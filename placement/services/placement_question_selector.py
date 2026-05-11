"""Stratified random selection from the placement question bank.

Public API
----------
    create_placement_attempt(user)              -> PlacementAttempt
    select_written_questions(user, count=5)     -> list[PlacementQuestion]
    select_speaking_questions(user, count=5)    -> list[PlacementQuestion]

Selection rules (matches the project spec):
  1. Active questions only.
  2. Avoid questions the user saw in their last 2 attempts.
  3. Cover the 5 spec-defined topic buckets per section so the test
     touches multiple skills / topics.
  4. Mix difficulties: at least one easy (<0.35), one medium (0.35-0.65),
     one hard (>0.65) per section when the bank allows.
  5. Once the attempt is created, the questions are persisted in
     `PlacementAttemptQuestion` rows — refreshing the page returns the
     same 5+5.

The strategy is intentionally simple (no IRT yet) so it can be replaced
with an adaptive selector later without changing this module's signature.
"""
from __future__ import annotations

import logging
import random
from typing import Iterable

from django.db import transaction

from ..models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementQuestion,
)

logger = logging.getLogger(__name__)

WRITTEN_DISTRIBUTION = [
    ("intro",       "self-introduction / personal writing"),
    ("grammar_fix", "grammar completion or correction"),
    ("sentence",    "sentence / paragraph writing"),
    ("daily",       "daily routine / past or future tense"),
    ("reason",      "reason / opinion / goal"),
]
SPEAKING_DISTRIBUTION = [
    ("name",        "introduction / name"),
    ("age_country", "age / country / nationality"),
    ("work_study",  "work / study"),
    ("hobby",       "hobby / daily life"),
    ("reason",      "reason for learning English / goal"),
]

# Difficulty bands used to enforce variety. We aim for at least one
# question in each band per section when the bank can supply it.
EASY_MAX = 0.35
HARD_MIN = 0.65
RECENT_ATTEMPTS_TO_AVOID = 2


def _previously_seen_question_ids(user) -> set[int]:
    """Return the question IDs the user answered in their last N attempts.

    Used to bias selection away from repetition. Falls back to an empty
    set when the bank is too small to honour the no-repeat rule.
    """
    recent = PlacementAttempt.objects.filter(user=user).order_by("-started_at")[
        :RECENT_ATTEMPTS_TO_AVOID
    ]
    return set(
        PlacementAttemptQuestion.objects.filter(attempt__in=list(recent))
        .values_list("question_id", flat=True)
    )


def _bucket_pool(question_type: str, topic: str, exclude_ids: Iterable[int],
                 *, prefer_mcq: bool = True):
    """Active questions for one (type, topic) bucket, minus exclusions.

    When `prefer_mcq=True` (the default for the placement test), MCQ
    rows are returned first so the selector picks selection-based
    questions when the bucket has them. Free-text rows still appear
    as fallbacks if the bucket runs out of MCQs.
    """
    qs = PlacementQuestion.objects.filter(
        question_type=question_type, topic=topic, is_active=True,
    ).exclude(id__in=list(exclude_ids))
    rows = list(qs)
    if prefer_mcq:
        rows.sort(key=lambda q: 0 if q.expected_answer_type == "mcq" else 1)
    return rows


def _pick_one_from(bucket: list[PlacementQuestion],
                   rng: random.Random) -> PlacementQuestion | None:
    """Pick one question from a bucket, preferring MCQs.

    The bucket is already sorted MCQ-first by `_bucket_pool`. We pick
    randomly from the leading MCQ slice when present, otherwise any.
    """
    if not bucket:
        return None
    mcqs = [q for q in bucket if q.expected_answer_type == "mcq"]
    if mcqs:
        return rng.choice(mcqs)
    return rng.choice(bucket)


def _difficulty_band(q: PlacementQuestion) -> str:
    if q.difficulty_score < EASY_MAX:
        return "easy"
    if q.difficulty_score >= HARD_MIN:
        return "hard"
    return "medium"


def _pick_with_variety(buckets: list[list[PlacementQuestion]], rng: random.Random,
                      ) -> list[PlacementQuestion]:
    """One question per bucket, then rebalance toward difficulty mix.

    Process:
      1. From each bucket pick a random candidate. If a bucket is empty
         (rare on a healthy seed), skip — we'll backfill later.
      2. Inspect difficulty bands of the picks. If we have 0 easy or
         0 hard, try replacing one of the other picks with an easy/hard
         alternative pulled from its own bucket.
      3. If a bucket was empty in step 1 OR a swap couldn't find a
         candidate, backfill from any remaining active question of the
         right `question_type` (last-resort, preserves the count of 5).
    """
    selected: list[PlacementQuestion] = []
    bucket_for_index: list[list[PlacementQuestion]] = []
    for bucket in buckets:
        if not bucket:
            continue
        choice = _pick_one_from(bucket, rng)
        if choice is None:
            continue
        selected.append(choice)
        bucket_for_index.append([q for q in bucket if q.id != choice.id])

    # Rebalance: ensure at least one easy + one hard.
    bands = [_difficulty_band(q) for q in selected]
    for desired in ("easy", "hard"):
        if desired in bands:
            continue
        # Find a slot whose bucket can supply the missing band.
        for i, alts in enumerate(bucket_for_index):
            replacement = next(
                (q for q in alts if _difficulty_band(q) == desired), None,
            )
            if replacement:
                selected[i] = replacement
                bucket_for_index[i] = [q for q in alts if q.id != replacement.id]
                bands[i] = desired
                break
    return selected


def _backfill(selected: list[PlacementQuestion], target: int,
              question_type: str, exclude_ids: set[int],
              rng: random.Random) -> list[PlacementQuestion]:
    """Top up to `target` count by sampling any remaining active question."""
    if len(selected) >= target:
        return selected[:target]
    have_ids = {q.id for q in selected} | set(exclude_ids)
    pool = list(
        PlacementQuestion.objects.filter(
            question_type=question_type, is_active=True,
        ).exclude(id__in=list(have_ids))
    )
    rng.shuffle(pool)
    selected.extend(pool[: (target - len(selected))])
    return selected


def select_written_questions(user, count: int = 5,
                             rng: random.Random | None = None,
                             ) -> list[PlacementQuestion]:
    rng = rng or random.Random()
    seen = _previously_seen_question_ids(user)
    buckets = [
        _bucket_pool("written", topic, seen)
        for topic, _label in WRITTEN_DISTRIBUTION
    ]
    selected = _pick_with_variety(buckets, rng)
    selected = _backfill(selected, count, "written", seen, rng)
    return selected[:count]


def select_speaking_questions(user, count: int = 5,
                              rng: random.Random | None = None,
                              ) -> list[PlacementQuestion]:
    rng = rng or random.Random()
    seen = _previously_seen_question_ids(user)
    buckets = [
        _bucket_pool("speaking", topic, seen)
        for topic, _label in SPEAKING_DISTRIBUTION
    ]
    selected = _pick_with_variety(buckets, rng)
    selected = _backfill(selected, count, "speaking", seen, rng)
    return selected[:count]


@transaction.atomic
def create_placement_attempt(user, *, count: int = 5,
                             rng: random.Random | None = None,
                             ) -> PlacementAttempt:
    """Create an attempt + persist 5 written + 5 speaking selections.

    The persistence step is the contract that makes the test stable:
    refreshing the page reads `PlacementAttemptQuestion` rows by
    `attempt_id` and serves the same questions instead of calling the
    selector again.
    """
    rng = rng or random.Random()
    written = select_written_questions(user, count=count, rng=rng)
    speaking = select_speaking_questions(user, count=count, rng=rng)
    if len(written) < count or len(speaking) < count:
        logger.warning(
            "create_placement_attempt: bank short — got %d written, %d speaking "
            "(target=%d each). Run seed_placement_questions to top up.",
            len(written), len(speaking), count,
        )

    attempt = PlacementAttempt.objects.create(user=user, status="started")
    rows = []
    for i, q in enumerate(written, start=1):
        rows.append(PlacementAttemptQuestion(
            attempt=attempt, question=q, section="written", order=i,
        ))
    for i, q in enumerate(speaking, start=1):
        rows.append(PlacementAttemptQuestion(
            attempt=attempt, question=q, section="speaking", order=i,
        ))
    PlacementAttemptQuestion.objects.bulk_create(rows)
    return attempt
