"""Expand a blueprint's `variables_schema` into iterable bindings.

Schema (kept minimal to stay auditable):
  {
    "subject": ["she", "he"],                 # inline list of strings
    "verb":    [["go","went","gone"], ...],   # inline list of tuples
    "place":   {"items": [...]},              # equivalent to bare list
  }

Two public surfaces:
  * `iter_bindings(schema)` — yields one binding dict per cartesian
    combination. Use this when you want exhaustive coverage and the
    cardinality is small enough to materialise.
  * `sample_bindings(schema, n, seed=...)` — yields N bindings via a
    deterministic random walk. Use this when the cartesian product is
    too large to enumerate (the common case).

Both honour deterministic seeds so the same call returns the same
bindings — important for reproducibility without persistence.
"""
from __future__ import annotations

import hashlib
import itertools
import random
from typing import Iterator


def _items_for(spec) -> list:
    """Schema entry → list of items. Accepts list or {'items': [...]}."""
    if isinstance(spec, dict):
        return list(spec.get("items") or [])
    if isinstance(spec, (list, tuple)):
        return list(spec)
    raise ValueError(f"Invalid variables_schema entry: {spec!r}")


def cardinality(schema: dict) -> int:
    """Cartesian product size — upper bound on unique bindings."""
    if not schema:
        return 0
    total = 1
    for v in schema.values():
        items = _items_for(v)
        if not items:
            return 0
        total *= len(items)
    return total


def iter_bindings(schema: dict) -> Iterator[dict]:
    """Enumerate every cartesian combination. Caller is responsible for
    not invoking this on schemas with billions of combinations."""
    if not schema:
        return
    keys = list(schema.keys())
    pools = [_items_for(schema[k]) for k in keys]
    for combo in itertools.product(*pools):
        yield {k: v for k, v in zip(keys, combo)}


def deterministic_seed(token: str, variant: int) -> int:
    h = hashlib.sha1(f"{token}:{variant}".encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def sample_bindings(
    schema: dict,
    *,
    n: int,
    seed_token: str = "qf",
    start_variant: int = 0,
) -> list[dict]:
    """Return up to N deterministically-sampled bindings.
    For each variant `i`, picks one item per variable using a seeded RNG."""
    if not schema:
        return []
    keys = list(schema.keys())
    pools = [_items_for(schema[k]) for k in keys]
    if any(len(p) == 0 for p in pools):
        return []
    out: list[dict] = []
    for i in range(n):
        rng = random.Random(deterministic_seed(seed_token, start_variant + i))
        out.append({k: rng.choice(p) for k, p in zip(keys, pools)})
    return out
