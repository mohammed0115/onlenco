"""On-demand question generation — the "infinite generator".

Scope:
- `generate_for_user(...)` returns a list of question dicts WITHOUT
  writing to the DB. Each dict carries a `seed_key` so the caller can
  later replay or record the view.
- `replay(seed_key)` re-renders the same question deterministically. No
  DB row required — the seed is the recipe.
- `record_view(user, seed_key, …)` is the one DB-writing path. It
  persists the seed (if not already stored) plus a UserSeedHistory row,
  so the next call to `generate_for_user` for that user will skip the
  same content.

Storage policy
--------------
A `QuestionSeed` row is created only when the seed is *manifested*:
 - the student answered the question (record_view called)
 - a reviewer approved it
 - it was used in an exam / benchmark
The full theoretical question space (templates × all variants) is never
written. With a 32-bit variant per blueprint and ~150 blueprints, the
*virtual* capacity is on the order of 10¹² items per blueprint; total
≈ 10¹⁴+ unique items reachable, all reproducible from O(seed_key).
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Iterable

from django.db import transaction
from django.db.models import F

from learning_core.models import GrammarTopic, StudentLearningProfile, UserWeakness

from . import question_validator
from .question_renderer import render
from .variable_expander import sample_bindings
from ..models import QuestionBlueprint, QuestionSeed, UserSeedHistory

logger = logging.getLogger(__name__)

DEFAULT_CEFR = "B1"
SEED_PREFIX = "sd"


# ---------------------------------------------------------------------------
# Seed key encoding (forward + reverse)
# ---------------------------------------------------------------------------

def encode_seed_key(blueprint_code: str, variant: int) -> str:
    return f"{SEED_PREFIX}:{blueprint_code}:{variant}"


def decode_seed_key(seed_key: str) -> tuple[str, int] | None:
    """Returns (blueprint_code, variant) or None if the key is malformed."""
    if not seed_key or not seed_key.startswith(f"{SEED_PREFIX}:"):
        return None
    parts = seed_key.split(":", 2)
    if len(parts) != 3:
        return None
    try:
        return parts[1], int(parts[2])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_with_variant(blueprint: QuestionBlueprint, variant: int) -> dict | None:
    """Deterministically render a single question dict for (blueprint, variant).

    Returns None when the blueprint's variables_schema is empty or the
    renderer fails (the caller should treat this as "skip this combo")."""
    schema = blueprint.variables_schema or {}
    bindings_list = sample_bindings(
        schema, n=1, seed_token=blueprint.code, start_variant=variant,
    )
    if not bindings_list:
        return None
    try:
        item = render(blueprint, bindings_list[0], variant=variant)
    except Exception as e:
        logger.warning("on_demand: render failed for %s v=%d: %s",
                       blueprint.code, variant, e)
        return None
    item["seed_key"] = encode_seed_key(blueprint.code, variant)
    item["variable_state"] = bindings_list[0]
    return item


# ---------------------------------------------------------------------------
# Blueprint selection
# ---------------------------------------------------------------------------

def _user_cefr_level(user) -> str | None:
    profile = StudentLearningProfile.objects.filter(user=user).first()
    if profile and profile.current_cefr_level:
        return profile.current_cefr_level
    return None


def _select_blueprints(
    *,
    cefr_level: str | None = None,
    skill: str | None = None,
    weakness: Any = None,
) -> list[QuestionBlueprint]:
    qs = QuestionBlueprint.objects.filter(is_active=True)
    if cefr_level:
        qs = qs.filter(cefr_level=cefr_level)
    if skill:
        qs = qs.filter(skill=skill)

    # `weakness` may be a UserWeakness, a string skill code, or a topic slug.
    if weakness is not None:
        if isinstance(weakness, UserWeakness):
            if weakness.skill_id and weakness.skill:
                qs = qs.filter(skill=weakness.skill.category)
            if weakness.grammar_topic_id:
                qs = qs.filter(grammar_topic_id=weakness.grammar_topic_id)
        elif isinstance(weakness, GrammarTopic):
            qs = qs.filter(grammar_topic_id=weakness.id)
        elif isinstance(weakness, str):
            # Treat as either a skill code or a grammar topic slug.
            from question_factory import constants as C
            valid_skills = {s for s, _ in C.SKILL_CHOICES}
            if weakness in valid_skills:
                qs = qs.filter(skill=weakness)
            else:
                qs = qs.filter(grammar_topic__slug=weakness)
    return list(qs)


# ---------------------------------------------------------------------------
# User-history dedup
# ---------------------------------------------------------------------------

def _user_seen_hashes(user, *, recent_limit: int = 1000) -> set[str]:
    """Most-recent N content_hashes the user has been shown.

    Capped at `recent_limit` so this stays fast for users with very long
    histories — older items are allowed to recycle, which is what you'd
    want for spaced repetition anyway."""
    if user is None or not getattr(user, "id", None):
        return set()
    return set(
        UserSeedHistory.objects
        .filter(user=user)
        .order_by("-seen_at")
        .values_list("content_hash", flat=True)[:recent_limit]
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class OnDemandQuestionService:
    """Stateless service. Methods are class methods so callers don't have
    to instantiate; the service holds no state between calls."""

    MAX_RENDER_ATTEMPTS_PER_ITEM = 6
    DEFAULT_VARIANT_BITS = 32

    @classmethod
    def generate_for_user(
        cls,
        user,
        *,
        cefr_level: str | None = None,
        skill: str | None = None,
        weakness: Any = None,
        count: int = 10,
        validate: bool = True,
        quality_threshold: int = 60,
    ) -> list[dict]:
        """Return up to `count` question dicts. **No DB writes.**

        Each dict has a `seed_key` that the caller can later pass to
        `record_view()` (when the student answers) or `replay()` (when
        the renderer needs to reconstruct the same question)."""
        target_level = cefr_level or _user_cefr_level(user) or DEFAULT_CEFR

        blueprints = _select_blueprints(
            cefr_level=target_level, skill=skill, weakness=weakness,
        )
        # If the narrow filter yields no blueprints, relax progressively
        # so the caller never gets back an empty list when *some*
        # blueprint at the user's level exists.
        if not blueprints and weakness is not None:
            blueprints = _select_blueprints(
                cefr_level=target_level, skill=skill,
            )
        if not blueprints and skill is not None:
            blueprints = _select_blueprints(cefr_level=target_level)
        if not blueprints:
            return []

        seen_hashes = _user_seen_hashes(user)
        results: list[dict] = []
        attempts = 0
        max_attempts = max(count * cls.MAX_RENDER_ATTEMPTS_PER_ITEM, 30)

        while len(results) < count and attempts < max_attempts:
            attempts += 1
            bp = blueprints[attempts % len(blueprints)]
            variant = secrets.randbits(cls.DEFAULT_VARIANT_BITS)
            item = _render_with_variant(bp, variant)
            if item is None:
                continue
            if validate:
                question_validator.annotate(item)
                if not question_validator.passes(item, threshold=quality_threshold):
                    continue
            ch = item.get("content_hash")
            if ch and ch in seen_hashes:
                continue
            seen_hashes.add(ch)  # also avoid duplicates within this batch
            results.append(item)
        return results

    # -----------------------------------------------------------------
    # Replay
    # -----------------------------------------------------------------

    @classmethod
    def replay(cls, seed_key: str) -> dict | None:
        """Re-render the question for `seed_key`.

        Works *without* needing a QuestionSeed row to exist — the seed
        key alone is sufficient because the renderer is deterministic.
        The DB is only consulted to look up the QuestionBlueprint."""
        decoded = decode_seed_key(seed_key)
        if decoded is None:
            return None
        bp_code, variant = decoded
        bp = QuestionBlueprint.objects.filter(code=bp_code, is_active=True).first()
        if bp is None:
            return None
        return _render_with_variant(bp, variant)

    # -----------------------------------------------------------------
    # Persistence (only when "used")
    # -----------------------------------------------------------------

    @classmethod
    def record_view(
        cls,
        user,
        seed_key: str,
        *,
        answered: bool = False,
        is_correct: bool | None = None,
    ) -> QuestionSeed | None:
        """Persist the seed (idempotent) + the user's view of it.

        This is the single place where on-demand items become DB rows.
        Call it when:
          - a student submits an answer (`answered=True`),
          - a reviewer approves the item,
          - the item is used in an exam or benchmark.
        """
        item = cls.replay(seed_key)
        if item is None:
            return None
        with transaction.atomic():
            seed, created = QuestionSeed.objects.get_or_create(
                seed_key=seed_key,
                defaults={
                    "blueprint_id": item["blueprint_id"],
                    "cefr_level": item.get("cefr_level") or "",
                    "skill": item.get("skill") or "",
                    "grammar_topic_id": item.get("grammar_topic_id"),
                    "difficulty_score": float(item.get("difficulty_score") or 0.5),
                    "variable_state": item.get("variable_state") or {},
                    "content_hash": item["content_hash"],
                },
            )
            if not created:
                # Atomic increment so concurrent record_view() calls don't race.
                QuestionSeed.objects.filter(pk=seed.pk).update(
                    generated_count=F("generated_count") + 1,
                )
                seed.refresh_from_db(fields=["generated_count", "last_used_at"])
            UserSeedHistory.objects.update_or_create(
                user=user, seed=seed,
                defaults={
                    "content_hash": seed.content_hash,
                    "answered": answered,
                    "is_correct": is_correct,
                },
            )
        return seed

    @classmethod
    def record_views_bulk(cls, user, seed_keys: Iterable[str]) -> int:
        """Record a list of seed_keys as 'seen but not answered' for one user.

        Useful when you delivered a batch and want to mark them as
        already-shown so the next batch doesn't repeat them, without
        waiting for individual answers."""
        n = 0
        for sk in seed_keys:
            if cls.record_view(user, sk, answered=False, is_correct=None):
                n += 1
        return n
