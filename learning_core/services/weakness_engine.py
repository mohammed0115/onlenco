"""Weakness Prediction Engine.

Aggregates UserError rows into UserWeakness records using a transparent,
rule-based scoring formula. Designed to be replaced or augmented by a
Naive-Bayes classifier later, but works deterministically with little data.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import timedelta
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from learning_core.models import UserError, UserWeakness


RECENT_WINDOW_DAYS = 30
LOOKBACK_LIMIT = 500

W_FREQUENCY = 0.5
W_SEVERITY = 0.4
W_RECENCY = 0.1

FREQUENCY_SCALE = 10  # frequency is normalized as min(freq / FREQUENCY_SCALE, 1.0)
DECAY_FACTOR = 0.4    # stale weakness priority is multiplied by this each run

RESOLVED_THRESHOLD = 5.0     # priority below this becomes "resolved"
IMPROVING_THRESHOLD = 25.0   # priority below this (and above resolved) becomes "improving"


def _recency_factor(when, now) -> float:
    """Return a 0..1 score that decays with age (half-life ~14 days)."""
    age_days = max(0.0, (now - when).total_seconds() / 86400.0)
    return float(math.exp(-age_days / 14.0))


def _bucket_key(error: UserError) -> tuple[int | None, int | None]:
    return (error.skill_id, error.grammar_topic_id)


def update_user_weaknesses(user) -> list[UserWeakness]:
    """Recompute UserWeakness rows for `user`. Returns the active weaknesses
    sorted by priority (descending)."""
    now = timezone.now()
    horizon = now - timedelta(days=RECENT_WINDOW_DAYS)

    recent_errors: Iterable[UserError] = (
        UserError.objects.filter(user=user, created_at__gte=horizon)
        .select_related("skill", "grammar_topic")
        .order_by("-created_at")[:LOOKBACK_LIMIT]
    )

    buckets: dict[tuple[int | None, int | None], list[UserError]] = defaultdict(list)
    for err in recent_errors:
        if err.skill_id is None and err.grammar_topic_id is None:
            continue  # untyped errors don't form a weakness bucket
        buckets[_bucket_key(err)].append(err)

    # Compute per-bucket stats
    metrics: dict[tuple[int | None, int | None], dict] = {}
    for key, errs in buckets.items():
        freq = len(errs)
        sev_avg = sum(e.severity for e in errs) / freq
        rec_score = sum(_recency_factor(e.created_at, now) for e in errs) / freq
        metrics[key] = {
            "frequency": freq,
            "severity_average": sev_avg,
            "recency_score": rec_score,
            "errors": errs,
        }

    # Normalize and compute priority. frequency is scaled against an absolute
    # baseline (FREQUENCY_SCALE) so a single mild error stays low-priority.
    priorities: dict[tuple[int | None, int | None], float] = {}
    for key, m in metrics.items():
        freq_norm = min(m["frequency"] / FREQUENCY_SCALE, 1.0)
        sev_norm = m["severity_average"] / 10.0         # 0..1
        rec_norm = m["recency_score"]                   # 0..1
        priority = (
            W_FREQUENCY * freq_norm
            + W_SEVERITY * sev_norm
            + W_RECENCY * rec_norm
        ) * 100.0
        priorities[key] = round(priority, 2)

    newly_active: list[UserWeakness] = []
    with transaction.atomic():
        # Update existing or create new rows
        seen_keys: set[tuple[int | None, int | None]] = set()
        active_rows: list[UserWeakness] = []

        for key, m in metrics.items():
            skill_id, topic_id = key
            seen_keys.add(key)
            priority = priorities[key]

            if priority < RESOLVED_THRESHOLD:
                status = "resolved"
            elif priority < IMPROVING_THRESHOLD:
                status = "improving"
            else:
                status = "active"

            existing = UserWeakness.objects.filter(
                user=user, skill_id=skill_id, grammar_topic_id=topic_id
            ).first()
            previous_status = existing.status if existing else None

            row, _ = UserWeakness.objects.update_or_create(
                user=user,
                skill_id=skill_id,
                grammar_topic_id=topic_id,
                defaults={
                    "weakness_score": min(100.0, priority * 1.0),
                    "frequency": m["frequency"],
                    "severity_average": round(m["severity_average"], 2),
                    "recency_score": round(m["recency_score"], 4),
                    "priority_score": priority,
                    "status": status,
                },
            )
            active_rows.append(row)
            if status == "active" and previous_status != "active":
                newly_active.append(row)

        # Decay rows that no longer have recent errors but still exist
        stale = (
            UserWeakness.objects.filter(user=user)
            .exclude(
                skill_id__in=[k[0] for k in seen_keys if k[0] is not None]
                if seen_keys
                else []
            )
            .exclude(
                grammar_topic_id__in=[k[1] for k in seen_keys if k[1] is not None]
                if seen_keys
                else []
            )
            .exclude(status="resolved")
        )
        for row in stale:
            # Drop priority each time, then re-bucket status
            new_priority = max(0.0, row.priority_score * DECAY_FACTOR)
            if new_priority < RESOLVED_THRESHOLD:
                row.status = "resolved"
            elif new_priority < IMPROVING_THRESHOLD:
                row.status = "improving"
            row.priority_score = round(new_priority, 2)
            row.weakness_score = min(100.0, row.priority_score)
            row.save(update_fields=["priority_score", "weakness_score", "status", "updated_at"])

    # Notify on newly-active weaknesses (one email per user per run, top one).
    if newly_active:
        try:
            top = sorted(newly_active, key=lambda r: r.priority_score, reverse=True)[0]
            label = (
                (top.grammar_topic.name if top.grammar_topic else None)
                or (top.skill.name if top.skill else "general")
            )
            from notifications import constants as C
            from notifications.services import NotificationService
            NotificationService().trigger(
                C.WEAKNESS_DETECTED,
                user=user,
                payload={
                    "topic": label,
                    "skill": top.skill.name if top.skill else "",
                    "cta_url": "/dashboard/",
                    "cta_label": "Practice now",
                    "dedup_key": f"weakness:{top.id}",
                },
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("weakness_detected notify failed: %s", e)

    return [
        r
        for r in sorted(active_rows, key=lambda r: r.priority_score, reverse=True)
        if r.status == "active"
    ]


def get_top_weaknesses(user, limit: int = 3) -> list[UserWeakness]:
    qs = (
        UserWeakness.objects.filter(user=user, status="active")
        .select_related("skill", "grammar_topic")
        .order_by("-priority_score", "-updated_at")[:limit]
    )
    return list(qs)
