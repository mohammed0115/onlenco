from __future__ import annotations

from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from payments.models import PaymentSubmission
from platform_admin.services.audit_log_service import log_action


def payment_queryset(params=None):
    qs = PaymentSubmission.objects.select_related("user", "user__profile", "reviewed_by").order_by("-created_at")
    params = params or {}
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(user__email__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__profile__full_name__icontains=q)
            | Q(transaction_reference__icontains=q)
        )
    status = (params.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    plan = (params.get("plan") or "").strip()
    if plan:
        qs = qs.filter(plan=plan)
    method = (params.get("method") or "").strip()
    if method:
        qs = qs.filter(method=method)
    return qs


def payment_metrics() -> dict:
    qs = PaymentSubmission.objects.all()
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "pending": qs.filter(status__in=["pending", "needs_review"]).count(),
        "approved": qs.filter(status="approved").count(),
        "rejected": qs.filter(status="rejected").count(),
        "revenue_month": qs.filter(status="approved", reviewed_at__gte=month_start).aggregate(total=Sum("amount_sdg"))["total"] or 0,
    }


def approve_payment(request, payment: PaymentSubmission):
    old_status = payment.status
    payment.approve(reviewer=request.user)
    log_action(
        request,
        action_type="payment.approve",
        target_user=payment.user,
        object_type="PaymentSubmission",
        object_id=payment.pk,
        description=f"Approved payment #{payment.pk}",
        metadata={"old_status": old_status, "plan": payment.plan, "amount_sdg": payment.amount_sdg},
    )


def reject_payment(request, payment: PaymentSubmission, reason: str):
    old_status = payment.status
    payment.reject(reviewer=request.user, note=reason)
    log_action(
        request,
        action_type="payment.reject",
        target_user=payment.user,
        object_type="PaymentSubmission",
        object_id=payment.pk,
        description=f"Rejected payment #{payment.pk}",
        metadata={"old_status": old_status, "reason": reason[:500]},
    )


def refund_payment(request, payment: PaymentSubmission, reason: str):
    """Reverse an approved payment and revoke the subscription it granted."""
    old_status = payment.status
    payment.refund(reviewer=request.user, reason=reason)
    log_action(
        request,
        action_type="payment.refund",
        target_user=payment.user,
        object_type="PaymentSubmission",
        object_id=payment.pk,
        description=f"Refunded payment #{payment.pk}",
        metadata={
            "old_status": old_status,
            "amount_sdg": payment.amount_sdg,
            "reason": reason[:500],
        },
    )


def extend_subscription(request, user, days: int):
    profile = user.profile
    now = timezone.now()
    starting = max(profile.subscription_expires_at or now, now)
    profile.subscription_expires_at = starting + timedelta(days=days)
    profile.subscription_status = "active"
    profile.save(update_fields=["subscription_status", "subscription_expires_at"])
    # Keep the plan-based quota in sync with the access flag, otherwise the
    # user is "subscribed" (can open premium pages) but resolves to NO plan
    # and therefore gets 0 AI/library minutes. Extend the current plan if any,
    # else attach the default plan so minutes actually work.
    try:
        from subscriptions.services import subscription_service
        existing = subscription_service.active_subscription_for(user)
        plan = existing.plan if existing else subscription_service.default_subscription_plan()
        if plan is not None:
            subscription_service.activate_subscription(user=user, plan=plan, duration_days=days)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "extend_subscription: plan sync failed for user %s", getattr(user, "pk", None))
    log_action(
        request,
        action_type="subscription.extend",
        target_user=user,
        object_type="Profile",
        object_id=profile.pk,
        description=f"Extended subscription by {days} days",
        metadata={"days": days, "expires_at": profile.subscription_expires_at.isoformat()},
    )


def expire_subscription(request, user):
    profile = user.profile
    profile.subscription_status = "expired"
    profile.subscription_expires_at = timezone.now()
    profile.save(update_fields=["subscription_status", "subscription_expires_at"])
    # Keep the new-style UserSubscription row in lock-step with the
    # legacy profile flag so AI-Tutor / library quota stop granting
    # minutes the moment the admin clicks "Expire subscription".
    try:
        from subscriptions.services import subscription_service
        subscription_service.revoke_subscriptions_for_user(user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "expire_subscription: revoke_subscriptions_for_user failed for user %s", user.pk,
        )
    log_action(
        request,
        action_type="subscription.expire",
        target_user=user,
        object_type="Profile",
        object_id=profile.pk,
        description="Expired subscription",
    )
