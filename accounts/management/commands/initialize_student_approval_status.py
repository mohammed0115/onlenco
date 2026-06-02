"""Initialize / reconcile approval_status for existing accounts.

Safe to re-run. Mirrors the data migration logic with reporting.

    python manage.py initialize_student_approval_status --dry-run
    python manage.py initialize_student_approval_status --confirm

Rules:
  * staff / superuser / admin-role / Teacher-group → approved (exempt)
  * email-verified students                        → approved
  * everyone else (unverified)                     → pending_email_verification
Never approves a student who is currently rejected/suspended.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import (
    APPROVAL_APPROVED, APPROVAL_PENDING_EMAIL, APPROVAL_REJECTED,
    APPROVAL_SUSPENDED, Profile,
)


class Command(BaseCommand):
    help = "Initialize approval_status for existing accounts (anti-bot gate)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true", dest="confirm")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        approved = pending = skipped_priv = suspicious = unchanged = 0

        for p in Profile.objects.select_related("user").iterator():
            # Never auto-flip a manually rejected/suspended account.
            if p.approval_status in (APPROVAL_REJECTED, APPROVAL_SUSPENDED):
                unchanged += 1
                continue
            if p.is_staff_or_privileged:
                target = APPROVAL_APPROVED
                skipped_priv += 1
            elif p.email_verified:
                target = APPROVAL_APPROVED
            else:
                target = APPROVAL_PENDING_EMAIL
            if p.suspicious_flags:
                suspicious += 1
            if target == APPROVAL_APPROVED:
                approved += 1
            else:
                pending += 1
            if p.approval_status != target and not dry_run:
                p.approval_status = target
                p.save(update_fields=["approval_status", "updated_at"])

        mode = "DRY-RUN (no changes)" if dry_run else "APPLIED"
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] approved={approved} pending={pending} "
            f"privileged_exempt={skipped_priv} suspicious={suspicious} "
            f"unchanged_rejected_or_suspended={unchanged}"))
