"""Payment service layer.

Reusable orchestration for payment submission and approval. Calls the
existing PaymentSubmission.approve() / reject() methods so the source of
truth stays on the model.
"""
from __future__ import annotations

from django.db import transaction

from .models import PaymentSubmission


@transaction.atomic
def approve_submission(submission: PaymentSubmission, reviewer, note: str = "") -> PaymentSubmission:
    if note:
        submission.admin_note = note
    submission.approve(reviewer)
    return submission


@transaction.atomic
def reject_submission(submission: PaymentSubmission, reviewer, note: str = "") -> PaymentSubmission:
    if note:
        submission.admin_note = note
    if hasattr(submission, "reject"):
        submission.reject(reviewer)
    else:
        from django.utils import timezone
        submission.status = "rejected"
        submission.reviewed_by = reviewer
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])
    return submission
