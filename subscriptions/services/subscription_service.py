"""Subscription lifecycle helpers.

The service centralizes the "which plan is this user on?" decision so
the rest of the codebase never has to reason about UserSubscription
rows directly. Sprint 2 wires the AI Tutor + Library Reader into
``active_plan_for(user)`` here.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from ..models import SubscriptionPlan, UserSubscription


User = get_user_model()


def active_subscription_for(user) -> Optional[UserSubscription]:
    """Most recent active UserSubscription for the user, or None."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    now = timezone.now()
    return (
        UserSubscription.objects
        .filter(user=user, status="active")
        .filter(models_query_active_until(now))
        .select_related("plan")
        .order_by("-start_date")
        .first()
    )


def models_query_active_until(now: datetime):
    """Q-object for ``end_date IS NULL OR end_date > now``."""
    from django.db.models import Q
    return Q(end_date__isnull=True) | Q(end_date__gt=now)


def active_plan_for(user) -> Optional[SubscriptionPlan]:
    sub = active_subscription_for(user)
    return sub.plan if sub else None


@transaction.atomic
def activate_subscription(
    *,
    user,
    plan: SubscriptionPlan,
    duration_days: int = 30,
    payment=None,
    auto_renew: bool = False,
) -> UserSubscription:
    """Create or extend an active subscription on ``plan`` for ``user``.

    If the user already has an active subscription on the same plan, the
    end_date is *extended* (top-up semantics) rather than starting a new
    row. Different plan → expire the old one and start fresh.
    """
    now = timezone.now()
    existing = active_subscription_for(user)
    if existing and existing.plan_id == plan.pk:
        base = existing.end_date or now
        existing.end_date = base + timedelta(days=duration_days)
        if auto_renew:
            existing.auto_renew = True
        if payment is not None:
            existing.payment = payment
        existing.save(update_fields=["end_date", "auto_renew", "payment", "updated_at"])
        return existing
    if existing:
        existing.status = "expired"
        existing.end_date = now
        existing.save(update_fields=["status", "end_date", "updated_at"])
    return UserSubscription.objects.create(
        user=user,
        plan=plan,
        status="active",
        start_date=now,
        end_date=now + timedelta(days=duration_days),
        auto_renew=auto_renew,
        payment=payment,
    )


def cancel_subscription(subscription: UserSubscription) -> UserSubscription:
    subscription.status = "cancelled"
    subscription.end_date = timezone.now()
    subscription.auto_renew = False
    subscription.save(update_fields=["status", "end_date", "auto_renew", "updated_at"])
    return subscription


def expire_overdue_subscriptions() -> int:
    """Cron-friendly sweep that flips status=expired for end_date <= now."""
    now = timezone.now()
    return UserSubscription.objects.filter(
        status="active",
        end_date__lte=now,
    ).update(status="expired", updated_at=now)
