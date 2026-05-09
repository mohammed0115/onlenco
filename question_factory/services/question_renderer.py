"""Pure-function renderer: blueprint + bindings → GeneratedQuestion dict.

DSL (string-only, allowlisted, no eval):
    var          → bound value (string or list)
    var.N        → element N of the bound value
    var.lower    → str.lower()
    var.upper    → str.upper()
    var.title    → str.title()
    a + b        → string concatenation
    'literal'    → string literal
    "literal"    → string literal
"""
from __future__ import annotations

import random
import re
from typing import Any

from . import duplicate_detector
from .variable_expander import deterministic_seed
from ..models import QuestionBlueprint
from .. import constants as C


_LITERAL_RE = re.compile(r"^['\"](.*)['\"]$")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*")
_PLACEHOLDER_RE = re.compile(
    r"\{(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\}"
)


def _resolve_token(token: str, bindings: dict[str, Any]) -> str:
    parts = token.split(".")
    head = parts[0]
    if head not in bindings:
        raise KeyError(f"Unknown binding: {head!r}")
    value: Any = bindings[head]
    for accessor in parts[1:]:
        if accessor.isdigit():
            idx = int(accessor)
            if not isinstance(value, (list, tuple)) or idx >= len(value):
                raise IndexError(f"Cannot index {head!r}.{accessor}")
            value = value[idx]
        elif accessor in ("lower", "upper", "title"):
            value = getattr(str(value), accessor)()
        else:
            raise ValueError(f"Unsupported accessor {accessor!r}")
    if isinstance(value, (list, tuple)):
        value = value[0]
    return str(value)


def evaluate_expression(expr: str, bindings: dict[str, Any]) -> str:
    parts = [p.strip() for p in expr.split("+")]
    out: list[str] = []
    for p in parts:
        m = _LITERAL_RE.match(p)
        if m:
            out.append(m.group(1))
            continue
        if not _TOKEN_RE.fullmatch(p):
            raise ValueError(f"Invalid expression segment: {p!r}")
        out.append(_resolve_token(p, bindings))
    return "".join(out)


def render_pattern(pattern: str, bindings: dict[str, Any]) -> str:
    return _PLACEHOLDER_RE.sub(
        lambda m: _resolve_token(m.group("name"), bindings), pattern,
    )


# -- distractor strategies ------------------------------------------------

def _morph_distractors(correct: str, k: int = 3) -> list[str]:
    base = correct.strip()
    out: list[str] = []
    if not base:
        return out
    if base.endswith("s") and len(base) > 2:
        out.append(base[:-1])
    else:
        out.append(base + "s")
    if not base.endswith("ing"):
        out.append(base + "ing")
    if not base.endswith("ed"):
        out.append(base + "ed")
    return [d for d in out if d != base][:k]


def _from_options_list(options_pool: list[str], correct: str,
                       rng: random.Random, k: int = 3) -> list[str]:
    pool = [str(o) for o in options_pool if str(o) != correct]
    rng.shuffle(pool)
    return pool[:k]


def _build_distractors(blueprint: QuestionBlueprint, bindings: dict,
                       correct: str, rng: random.Random) -> list[str]:
    meta = blueprint.metadata or {}
    cfg = meta.get("distractor_config") or {}
    strategy = cfg.get("strategy") or "morph"
    if strategy == "static":
        return [d for d in (cfg.get("options") or []) if d != correct]
    if strategy == "morph":
        return _morph_distractors(correct)
    if strategy == "from_binding":
        # Pull distractors from the same binding tuple (e.g. verb tuple
        # has [base, past, gerund] — past is correct, others distractors).
        var_name = cfg.get("variable", "")
        bound = bindings.get(var_name)
        if isinstance(bound, (list, tuple)):
            return [str(x) for x in bound if str(x) != correct][:3]
        return _morph_distractors(correct)
    if strategy == "from_pool":
        return _from_options_list(cfg.get("pool") or [], correct, rng)
    return _morph_distractors(correct)


# -- public surface ------------------------------------------------------

def render(
    blueprint: QuestionBlueprint,
    bindings: dict[str, Any],
    *,
    variant: int = 0,
) -> dict:
    """Render one question dict for a (blueprint, bindings, variant) tuple.

    Deterministic: same (blueprint.code, variant, bindings) always returns
    the same dict — distractor order included, because the RNG is seeded
    by the same token."""
    rng = random.Random(deterministic_seed(blueprint.code, variant))

    question_text = render_pattern(blueprint.template_pattern, bindings)
    correct = evaluate_expression(blueprint.expected_answer_pattern, bindings)
    explanation = ""
    if blueprint.explanation_pattern:
        explanation = render_pattern(blueprint.explanation_pattern, bindings)

    distractors: list[str] = []
    options: list[str] = []
    if blueprint.question_type == "multiple_choice":
        distractors = _build_distractors(blueprint, bindings, correct, rng)
        options = [correct] + distractors
        rng.shuffle(options)

    code = f"qf:{blueprint.code}:v{variant}"
    content_hash = duplicate_detector.hash_question(question_text, correct)
    difficulty = (blueprint.difficulty_min + blueprint.difficulty_max) / 2.0

    return {
        "code": code,
        "blueprint_id": blueprint.id,
        "blueprint_code": blueprint.code,
        "cefr_level": blueprint.cefr_level or "",
        "skill": blueprint.skill or "",
        "question_type": blueprint.question_type,
        "grammar_topic_id": blueprint.grammar_topic_id,
        "vocabulary_topic": blueprint.vocabulary_topic or "",
        "difficulty_score": difficulty,
        "question_text": question_text,
        "options": options,
        "correct_answer": correct,
        "acceptable_answers": [correct],
        "explanation": explanation,
        "feedback_correct": "Correct!",
        "feedback_wrong": f"The correct answer is '{correct}'.",
        "generated_by": C.GEN_TEMPLATE,
        "content_hash": content_hash,
        "metadata": {
            "blueprint_code": blueprint.code,
            "variant": variant,
            "bindings": {
                k: (v[0] if isinstance(v, (list, tuple)) else v)
                for k, v in bindings.items()
            },
        },
    }
