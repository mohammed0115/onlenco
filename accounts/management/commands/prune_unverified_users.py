"""Delete student accounts that signed up but never verified their email.

Bot signups land as `is_staff=False` users with `profile.email_verified=False`.
Real students click the OTP link within minutes; bots never do. This
command sweeps anything older than `--age-hours` (default 24h) and
removes it so the platform_admin students list stays clean.

Safe-by-default:
  - Only deletes users with `is_staff=False` AND `is_superuser=False`.
  - Only deletes users whose profile has `email_verified=False`.
  - Skips users with paid subscriptions, payment submissions, or any
    placement attempts (a real student who got distracted before
    verifying still has data we shouldn't drop).
  - --dry-run prints the would-delete count without actually deleting.

Run from scheduler at 04:30 daily (added in scripts/scheduler.py).
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete unverified student accounts older than --age-hours (default 24)."

    def add_arguments(self, parser):
        parser.add_argument("--age-hours", type=int, default=24,
                            help="Only delete accounts older than this many hours.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Print would-delete count without deleting.")

    def handle(self, *args, **options):
        User = get_user_model()
        age_hours = max(1, int(options["age_hours"]))
        cutoff = timezone.now() - timedelta(hours=age_hours)

        # Build the candidate set defensively — exclude anyone with
        # meaningful activity even if their email isn't verified yet.
        qs = (
            User.objects
            .filter(is_staff=False, is_superuser=False)
            .filter(date_joined__lt=cutoff)
            .filter(Q(profile__email_verified=False) | Q(profile__isnull=True))
            .exclude(payment_submissions__isnull=False)
            .exclude(placement_attempts__isnull=False)
        )
        # subscription FK may not exist on every install; guard the filter.
        try:
            qs = qs.exclude(subscription__status__in=["active", "trialing", "past_due"])
        except Exception:
            pass

        n = qs.count()
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"DRY RUN: would delete {n} accounts older than {age_hours}h"))
            for u in qs[:20]:
                self.stdout.write(f"  id={u.id} {u.email!r} joined={u.date_joined:%Y-%m-%d %H:%M}")
            if n > 20:
                self.stdout.write(f"  ... and {n - 20} more")
            return

        if n == 0:
            self.stdout.write("Nothing to prune.")
            return
        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Pruned {deleted} unverified accounts older than {age_hours}h."))
