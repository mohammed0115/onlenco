from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


PAYMENT_METHODS = [
    ("bankak", "Bankak"),
    ("fawry",  "Fawry"),
    ("ocash",  "O-Cash"),
]

PLANS = [
    ("monthly",   "Monthly"),
    ("quarterly", "Quarterly"),
]

PLAN_DETAILS = {
    "monthly":   {"price_sdg": 30000, "duration_days": 30},
    "quarterly": {"price_sdg": 50000, "duration_days": 90},
}

# Legacy plan strings → new SubscriptionPlan codes (Sprint 1+ data layer).
# When the legacy ``monthly`` payment is approved we ALSO activate the
# matching new-style subscription so the AI-Tutor / Library quotas kick
# in. ``quarterly`` defaults to the same plan code but for 90 days.
LEGACY_PLAN_TO_NEW_CODE = {
    "monthly":   "basic_10m",
    "quarterly": "basic_10m",
}

PAYMENT_STATUSES = [
    ("pending",      "Pending review"),
    ("needs_review", "Needs admin review"),
    ("approved",     "Approved"),
    ("rejected",     "Rejected"),
    ("refunded",     "Refunded"),
]


class PaymentMethodAccount(models.Model):
    """Bank/wallet account details shown to students for offline transfer.

    Editable by admins via /admin/ so account numbers can change without
    a code deploy. Each method (Bankak/Fawry/O-Cash) has at most one
    active row at a time.
    """

    method = models.CharField(max_length=10, choices=PAYMENT_METHODS, unique=True)
    label = models.CharField(max_length=80, help_text="Display name, e.g. 'Bankak'")
    account_number = models.CharField(
        max_length=80,
        help_text="Account number, IBAN, or phone number to send to.",
    )
    account_holder = models.CharField(
        max_length=120,
        default="Onlenco Sudan",
        help_text="Name on the account.",
    )
    instructions = models.TextField(
        blank=True,
        help_text="Optional extra instructions shown under the account info.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "method"]
        verbose_name = _("Payment method account")
        verbose_name_plural = _("Payment method accounts")

    def __str__(self):
        return f"{self.label} - {self.account_number}"


class PaymentSubmission(models.Model):
    """A user-submitted payment proof.

    The Sudan payment flow from section 4 of the technical doc:
      1. user picks plan + method
      2. user transfers money offline to the corresponding account
      3. user uploads a screenshot of the transfer
      4. an admin reviews and approves/rejects
      5. on approval, the user's profile.subscription_status flips to
         `active` and `subscription_expires_at` is set
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_submissions",
    )
    plan = models.CharField(max_length=12, choices=PLANS)
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    transaction_reference = models.CharField(
        max_length=120, blank=True,
        help_text="Reference number printed on the receipt or transfer SMS.",
    )
    amount_sdg = models.PositiveIntegerField()
    screenshot = models.ImageField(upload_to="payment_proofs/%Y/%m/")
    status = models.CharField(max_length=15, choices=PAYMENT_STATUSES, default="pending")

    admin_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_payments",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    # Refund trail — set when an approved payment is reversed.
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="refunded_payments",
    )
    refunded_at = models.DateTimeField(blank=True, null=True)
    refund_reason = models.TextField(blank=True)

    # --- Marketplace revenue split (Prompt 1) --------------------------
    # Filled in on approval: the SDG split between the student's chosen
    # teacher and the platform. Both default to 0; when no teacher is
    # selected the whole amount lands in platform_earnings.
    teacher_earnings = models.PositiveIntegerField(default=0)
    platform_earnings = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Payment submission")
        verbose_name_plural = _("Payment submissions")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} – {self.plan} – {self.status}"

    def approve(self, reviewer):
        """Approve and activate. If the user already has time left,
        extend rather than overwrite so top-ups stack.

        Also creates / extends a ``subscriptions.UserSubscription`` row on
        the matching SubscriptionPlan so the AI-Tutor + Library quotas
        unlock. Failure of the new-style activation NEVER blocks the
        legacy approve — we want admins to still ship the payment even
        if the plan mapping is mis-configured.
        """
        # Idempotency guard: a second approve() on the same submission
        # used to extend the subscription by another full cycle, which
        # gave admins an accidental "click twice = free month".
        if self.status == "approved":
            return
        now = timezone.now()
        days = PLAN_DETAILS[self.plan]["duration_days"]

        profile = self.user.profile
        starting = max(profile.subscription_expires_at or now, now)
        profile.subscription_expires_at = starting + timedelta(days=days)
        profile.subscription_status = "active"
        profile.save(update_fields=["subscription_status", "subscription_expires_at"])

        self.status = "approved"
        self.reviewed_by = reviewer
        self.reviewed_at = now
        self.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        self._record_revenue_split()

        self._activate_subscriptions_plan(duration_days=days)

        try:
            from notifications import constants as C
            from notifications.services import NotificationService
            NotificationService().trigger(
                C.PAYMENT_APPROVED,
                user=self.user,
                actor=reviewer,
                payload={
                    "plan": self.plan,
                    "amount_sdg": self.amount_sdg,
                    "expires_at": profile.subscription_expires_at.strftime("%Y-%m-%d") if profile.subscription_expires_at else "",
                    "cta_url": "/dashboard/",
                    "cta_label": "Open dashboard",
                    "dedup_key": f"approve:{self.id}",
                },
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("notify approve failed")

    def _record_revenue_split(self) -> None:
        """Split ``amount_sdg`` between the student's chosen teacher and the
        platform. Defensive: any failure leaves the whole amount with the
        platform so an approval is never blocked by the marketplace layer.
        """
        amount = int(self.amount_sdg or 0)
        teacher_cut, platform_cut = 0, amount
        try:
            from teacher_portal.models import StudentTeacherRelation
            relation = StudentTeacherRelation.active_for(self.user)
            tp = getattr(relation.teacher, "teacher_profile", None) if relation else None
            if tp is not None:
                teacher_cut = tp.teacher_share(amount)
                platform_cut = amount - teacher_cut
        except Exception:
            import logging
            logging.getLogger(__name__).exception("revenue split failed; defaulting to platform")
            teacher_cut, platform_cut = 0, amount
        self.teacher_earnings = teacher_cut
        self.platform_earnings = platform_cut
        self.save(update_fields=["teacher_earnings", "platform_earnings"])

    def _activate_subscriptions_plan(self, *, duration_days: int) -> None:
        """Spin up / extend the new-style UserSubscription. Best-effort."""
        try:
            from subscriptions.models import SubscriptionPlan
            from subscriptions.services import subscription_service
        except Exception:
            return
        plan_code = LEGACY_PLAN_TO_NEW_CODE.get(self.plan, self.plan)
        plan = SubscriptionPlan.objects.filter(code=plan_code, is_active=True).first()
        if plan is None:
            return
        try:
            subscription_service.activate_subscription(
                user=self.user,
                plan=plan,
                duration_days=duration_days,
                payment=self,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "PaymentSubmission.approve: subscription activation failed for %s", self.pk,
            )

    def reject(self, reviewer, note=""):
        self.status = "rejected"
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        if note:
            self.admin_note = note
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])

        profile = self.user.profile
        still_pending = self.user.payment_submissions.filter(status="pending").exists()
        if profile.subscription_status == "pending" and not still_pending:
            profile.subscription_status = "inactive"
            profile.save(update_fields=["subscription_status"])

        try:
            from notifications import constants as C
            from notifications.services import NotificationService
            NotificationService().trigger(
                C.PAYMENT_REJECTED,
                user=self.user,
                actor=reviewer,
                payload={
                    "plan": self.plan,
                    "amount_sdg": self.amount_sdg,
                    "reason": note or "Please re-submit a clearer screenshot.",
                    "next_action": "Re-submit a clearer screenshot or try another method.",
                    "cta_url": "/payments/subscribe/",
                    "cta_label": "Try again",
                    "dedup_key": f"reject:{self.id}",
                },
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("notify reject failed")

    def refund(self, reviewer, reason=""):
        """Reverse an approved payment: mark it refunded and revoke the
        subscription access it granted.

        Used when money is returned to the student — a duplicate
        payment, an admin error, or a cancellation. The refund trail
        (who / when / why) is stored on the row for the audit record.
        """
        now = timezone.now()
        self.status = "refunded"
        self.refunded_by = reviewer
        self.refunded_at = now
        self.refund_reason = reason
        self.save(update_fields=[
            "status", "refunded_by", "refunded_at", "refund_reason",
        ])

        # Money returned → end the subscription this payment unlocked.
        profile = self.user.profile
        profile.subscription_status = "expired"
        profile.subscription_expires_at = now
        profile.save(update_fields=["subscription_status", "subscription_expires_at"])

        # Also expire the new-style UserSubscription this payment unlocked
        # so active_plan_for() and the AI-Tutor quota check no longer
        # treat the refunded user as a paying customer.
        try:
            from subscriptions.services import subscription_service
            subscription_service.revoke_subscription_for_payment(self)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "PaymentSubmission.refund: revoke_subscription_for_payment failed for %s", self.pk,
            )
