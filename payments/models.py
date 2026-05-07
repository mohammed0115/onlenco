from datetime import timedelta

from django.conf import settings
from django.db import models
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

PAYMENT_STATUSES = [
    ("pending",      "Pending review"),
    ("needs_review", "Needs admin review"),
    ("approved",     "Approved"),
    ("rejected",     "Rejected"),
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
        verbose_name = "Payment method account"
        verbose_name_plural = "Payment method accounts"

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

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} – {self.plan} – {self.status}"

    def approve(self, reviewer):
        """Approve and activate. If the user already has time left,
        extend rather than overwrite so top-ups stack."""
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
