"""Template engine: render a `QuestionTemplate × banks` into a question dict.

This module is intentionally pure — no DB writes — so it can be reused by:
  * `factory_generate` (writes approved items via promotion_service)
  * `factory_variations` (on-demand variations, never persisted)
  * tests, fuzzers, dataset builders.

Expression DSL (kept tiny to stay safe — no eval()):
    var          → the bound bank value (string or list)
    var.N        → element N of the bound value (when it's a list/tuple)
    var.lower    → str.lower()
    var.upper    → str.upper()
    var.title    → str.title()
    a + b        → string concatenation (with whitespace allowed)
    'literal'    → string literal
    "literal"    → string literal

Anything fancier should live in a dedicated subclass — keeping the surface
small means the templates remain easy to audit.
"""
from __future__ import annotations

import hashlib
import random
import re
from typing import Any, Iterable

from ..models import QuestionTemplate, SubstitutionBank


# ---------------------------------------------------------------------------
# Bank loading + caching
# ---------------------------------------------------------------------------

def _load_banks(names: Iterable[str]) -> dict[str, list]:
    """Bulk-load banks by name; returns {name: items}. Missing banks are
    surfaced loudly — the engine refuses to render a template with a
    dangling reference."""
    rows = list(SubstitutionBank.objects.filter(name__in=list(names), is_active=True))
    by_name = {r.name: list(r.items or []) for r in rows}
    missing = set(names) - set(by_name)
    if missing:
        raise ValueError(f"Missing or inactive substitution banks: {sorted(missing)}")
    return by_name


# ---------------------------------------------------------------------------
# DSL evaluator (string-only, deterministic, allowlisted)
# ---------------------------------------------------------------------------

_LITERAL_RE = re.compile(r"^['\"](.*)['\"]$")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*")
_PLACEHOLDER_RE = re.compile(r"\{(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\}")


def _resolve_token(token: str, bindings: dict[str, Any]) -> str:
    """Resolve `var` / `var.N` / `var.lower` against the bound bindings."""
    parts = token.split(".")
    head = parts[0]
    if head not in bindings:
        raise KeyError(f"Unknown binding: {head!r}")
    value: Any = bindings[head]
    for accessor in parts[1:]:
        if accessor.isdigit():
            idx = int(accessor)
            if not isinstance(value, (list, tuple)) or idx >= len(value):
                raise IndexError(
                    f"Cannot index {head!r}.{accessor} — value is {type(value).__name__}"
                )
            value = value[idx]
        elif accessor == "lower":
            value = str(value).lower()
        elif accessor == "upper":
            value = str(value).upper()
        elif accessor == "title":
            value = str(value).title()
        else:
            raise ValueError(f"Unsupported accessor {accessor!r} on {head!r}")
    if isinstance(value, (list, tuple)):
        # Return the first element by default for unindexed list bindings —
        # the most common case is a tuple bank where index 0 is canonical.
        value = value[0]
    return str(value)


def evaluate_expression(expr: str, bindings: dict[str, Any]) -> str:
    """Evaluate a DSL expression against bindings.

    Supports `a + b + 'lit'` style concat and the accessor grammar above.
    """
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
    """Substitute `{var}` / `{var.N}` placeholders in a free-text pattern."""
    def repl(m):
        return _resolve_token(m.group("name"), bindings)
    return _PLACEHOLDER_RE.sub(repl, pattern)


# ---------------------------------------------------------------------------
# Distractor strategies
# ---------------------------------------------------------------------------

def _morph_distractors(correct: str) -> list[str]:
    """Programmatic perturbations of the correct answer — useful for verbs."""
    base = correct.strip()
    out = set()
    if not base:
        return []
    # singular/plural flip
    if base.endswith("s") and len(base) > 2:
        out.add(base[:-1])
    else:
        out.add(base + "s")
    # gerund-ish
    if not base.endswith("ing"):
        out.add(base + "ing")
    # past-ish
    if not base.endswith("ed"):
        out.add(base + "ed")
    return [d for d in out if d != base][:3]


def _bank_distractors(banks: dict[str, list], cfg: dict, correct: str,
                      rng: random.Random, n: int = 3) -> list[str]:
    bank_name = cfg.get("bank")
    if not bank_name or bank_name not in banks:
        return []
    pool = [str(x[0]) if isinstance(x, (list, tuple)) else str(x)
            for x in banks[bank_name]]
    pool = [p for p in pool if p and p != correct]
    rng.shuffle(pool)
    return pool[:n]


def _build_distractors(template: QuestionTemplate, banks: dict[str, list],
                       correct: str, rng: random.Random) -> list[str]:
    strategy = template.distractor_strategy
    cfg = template.distractor_config or {}
    if strategy == "static":
        return [str(d) for d in (cfg.get("options") or []) if d != correct]
    if strategy == "morph":
        return _morph_distractors(correct)
    if strategy == "from_bank":
        return _bank_distractors(banks, cfg, correct, rng)
    if strategy == "ai":
        # AI-generated distractors are produced by the LLM router on demand;
        # the engine alone returns an empty list — the caller decides
        # whether to fill via the router.
        return []
    return []


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def deterministic_seed(template_code: str, variant: int) -> int:
    """Stable per-(template, variant) seed so the same call always yields
    the same item — important for on-demand reproducibility without a DB."""
    h = hashlib.sha1(f"{template_code}:{variant}".encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def _bind_one(banks: dict[str, list], variables: dict[str, str],
              rng: random.Random) -> dict[str, Any]:
    """Pick one row from each bound bank."""
    return {var: rng.choice(banks[bank]) for var, bank in variables.items()}


def render_one(template: QuestionTemplate, *, variant: int = 0,
               bank_cache: dict[str, list] | None = None) -> dict:
    """Render a single question dict from the template.

    Deterministic for a given (template.code, variant) pair so the same
    call reproduces the same item — this is what lets us treat templates
    as a virtual question source of unbounded size without persistence.
    """
    bank_names = list({*template.variables.values(),
                       *([template.distractor_config.get("bank")]
                         if template.distractor_strategy == "from_bank" else [])})
    bank_names = [b for b in bank_names if b]
    banks = bank_cache if bank_cache is not None else _load_banks(bank_names)

    rng = random.Random(deterministic_seed(template.code, variant))
    bindings = _bind_one(banks, template.variables, rng)

    question_text = render_pattern(template.pattern, bindings)
    correct = evaluate_expression(template.correct_answer_expression, bindings)
    distractors = _build_distractors(template, banks, correct, rng)

    options: list[str] = []
    if template.question_type == "multiple_choice":
        options = [correct] + distractors
        rng.shuffle(options)

    explanation = ""
    if template.explanation_pattern:
        explanation = render_pattern(template.explanation_pattern, bindings)

    return {
        "code": f"tpl:{template.code}:v{variant}",
        "topic_slug": template.topic.slug,
        "topic_kind": template.topic.kind,
        "cefr_level": template.cefr_level or template.topic.cefr_level,
        "question_type": template.question_type,
        "difficulty_score": template.difficulty_score,
        "question": question_text,
        "options": options,
        "correct_answer": correct,
        "acceptable_answers": [correct],
        "explanation": explanation,
        "feedback_correct": "Correct!",
        "feedback_wrong": f"The correct answer is '{correct}'.",
        "estimated_time_seconds": template.estimated_time_seconds,
        "points": template.points,
        "language": "en",
        "metadata": {
            "template_code": template.code,
            "template_version": template.version,
            "variant": variant,
            "bindings": {k: (v[0] if isinstance(v, (list, tuple)) else v)
                         for k, v in bindings.items()},
        },
    }


def render_many(template: QuestionTemplate, *, count: int,
                start_variant: int = 0) -> list[dict]:
    """Render `count` items from one template using consecutive variants.
    Bank loading is amortised across the call."""
    bank_names = list({*template.variables.values(),
                       *([template.distractor_config.get("bank")]
                         if template.distractor_strategy == "from_bank" else [])})
    bank_names = [b for b in bank_names if b]
    bank_cache = _load_banks(bank_names)
    return [
        render_one(template, variant=start_variant + i, bank_cache=bank_cache)
        for i in range(count)
    ]


def maximum_variations(template: QuestionTemplate) -> int:
    """Approximate distinct items the template can yield — product of
    bound bank sizes. Useful for the operator before running generation."""
    bank_names = list(template.variables.values())
    if not bank_names:
        return 0
    sizes = list(
        SubstitutionBank.objects
        .filter(name__in=bank_names, is_active=True)
        .values_list("name", "items"),
    )
    by_name = {n: len(i or []) for n, i in sizes}
    total = 1
    for v in template.variables.values():
        total *= max(1, by_name.get(v, 0))
    return total
