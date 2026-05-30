"""XPTransaction-aware wrapper around the existing UserXP aggregator.

Phase 5 ships a per-event ledger so we can answer:
  * Show me how the student earned today's 80 XP — breakdown by source.
  * Did we already credit this answer? (idempotency).
  * Has this user ever been double-awarded? (audit).

Public API:
  * `award_xp(user, amount, source_type, source_id, reason="", metadata=None)`
    Creates a row in XPTransaction (idempotent on user+source_type+source_id
    when source_id is non-empty), then credits UserXP via the legacy
    `motivation.xp_service.award_xp`.

  * `has_awarded(user, source_type, source_id)` — convenience check.

  * `xp_breakdown_for_session(challenge_session)` — { "answers": 50,
    "completion": 20, "perfect": 10, "daily_goal": 25, "badges": 50,
    "total": 155 }.

This module wraps `motivation.xp_service.award_xp` rather than
duplicating it — the older callers still work unchanged, and Phase 5
gets idempotent ledger semantics on top.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.db import IntegrityError, transaction

from ..models import XPTransaction
from . import xp_service as legacy_xp


logger = logging.getLogger(__name__)


@transaction.atomic
def award_xp(
    user,
    amount: int,
    *,
    source_type: str,
    source_id: str | int = "",
    reason: str = "",
    metadata: Optional[dict] = None,
) -> Optional[XPTransaction]:
    """Grant XP and persist the ledger row.

    Returns the new XPTransaction, or `None` if a duplicate grant for
    the same (user, source_type, source_id) already exists — in that
    case we credit nothing (the ledger is the source of truth).

    `amount=0` is a no-op (still returns None) — keeps callers terse.
    """
    if amount == 0:
        return None
    sid = str(source_id) if source_id is not None else ""
    if sid:
        existing = XPTransaction.objects.filter(
            user=user, source_type=source_type, source_id=sid,
        ).first()
        if existing is not None:
            return None
    try:
        tx = XPTransaction.objects.create(
            user=user,
            amount=amount,
            source_type=source_type,
            source_id=sid,
            reason=reason or source_type,
            metadata=metadata or {},
        )
    except IntegrityError:
        # Race: another worker booked the same source — treat as no-op.
        logger.info(
            "XP race resolved as no-op (user=%s source=%s/%s)",
            getattr(user, "pk", None), source_type, sid,
        )
        return None
    # Credit the aggregate. Negative amounts are passed through as-is so
    # corrections still subtract — the legacy service guards on <= 0
    # by returning early, so we adjust totals ourselves for negatives.
    if amount > 0:
        legacy_xp.award_xp(user, amount, reason=reason or source_type)
    else:
        # Subtract from totals — legacy doesn't support negatives.
        from ..models import UserXP
        with transaction.atomic():
            xp_row, _ = UserXP.objects.select_for_update().get_or_create(user=user)
            xp_row.total_xp = max(0, (xp_row.total_xp or 0) + amount)
            xp_row.save(update_fields=["total_xp"])
    return tx


def has_awarded(user, source_type: str, source_id: str | int) -> bool:
    sid = str(source_id) if source_id is not None else ""
    if not sid:
        return False
    return XPTransaction.objects.filter(
        user=user, source_type=source_type, source_id=sid,
    ).exists()


def xp_breakdown_for_session(challenge_session) -> dict:
    """Group the session's XPTransactions by source_type for the Summary UI."""
    rows = XPTransaction.objects.filter(
        user=challenge_session.user,
    ).filter(
        metadata__challenge_session=challenge_session.pk,
    )
    breakdown: dict[str, int] = {}
    for row in rows:
        breakdown[row.source_type] = breakdown.get(row.source_type, 0) + row.amount
    breakdown["total"] = sum(v for k, v in breakdown.items() if k != "total")
    return breakdown
