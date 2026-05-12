"""Generate daily learning plans for active students.

Usage:
    python manage.py generate_daily_learning_plans --all-active
    python manage.py generate_daily_learning_plans --user-id 5
    python manage.py generate_daily_learning_plans --level A0
    python manage.py generate_daily_learning_plans --dry-run
    python manage.py generate_daily_learning_plans --date 2026-05-12

The command is idempotent — running it twice on the same day for the
same user does NOT create duplicate plans (unique constraint on
(user, date)). Pass `--force` to delete + regenerate.
"""
from __future__ import annotations

import datetime as dt
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from daily_learning.services.daily_plan_generator import generate_for_user

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate today's daily learning plan for one or many students."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            help="ISO date (YYYY-MM-DD). Defaults to today.",
        )
        parser.add_argument(
            "--user-id", type=int,
            help="Generate for one specific user id.",
        )
        parser.add_argument(
            "--all-active", action="store_true",
            help="Generate for every active student (onboarding_completed + not staff).",
        )
        parser.add_argument(
            "--level",
            help="Limit to users at this CEFR level (e.g. A0, B1).",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="Delete + regenerate existing plans for the date.",
        )
        parser.add_argument(
            "--no-ai", action="store_true",
            help="Force AI off for this run, regardless of settings.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Don't write anything — just print what would happen.",
        )

    def handle(self, *args, **opts):
        target_date = self._parse_date(opts.get("date"))
        users = self._select_users(opts)
        if not users:
            self.stdout.write(self.style.WARNING(
                "No users matched the filters; nothing to do."
            ))
            return

        if opts["dry_run"]:
            self.stdout.write(
                f"[DRY RUN] Would generate plans for {len(users)} user(s) "
                f"on {target_date}."
            )
            return

        allow_ai: bool | None = False if opts.get("no_ai") else None

        succeeded = 0
        failed = 0
        for user in users:
            try:
                plan = generate_for_user(
                    user, on_date=target_date,
                    force=opts.get("force", False),
                    allow_ai=allow_ai,
                )
                self.stdout.write(
                    f"  ✓ {user.email or user.username} → plan id={plan.id} "
                    f"({plan.plan_type}, {plan.items.count()} items)"
                )
                succeeded += 1
            except Exception as e:
                failed += 1
                self.stderr.write(self.style.ERROR(
                    f"  ✗ {user.email or user.username}: {e}"
                ))
                logger.exception("plan generation failed for user_id=%s", user.id)

        self.stdout.write(self.style.SUCCESS(
            f"Done. {succeeded} succeeded, {failed} failed."
        ))

    # --- helpers ----------------------------------------------------

    def _parse_date(self, value: str | None) -> dt.date:
        if not value:
            return timezone.localdate()
        try:
            return dt.date.fromisoformat(value)
        except Exception as e:
            raise CommandError(f"Invalid --date '{value}': {e}")

    def _select_users(self, opts) -> list:
        qs = User.objects.filter(is_active=True)
        if opts.get("user_id"):
            user = qs.filter(id=opts["user_id"]).first()
            if not user:
                raise CommandError(f"No active user with id={opts['user_id']}")
            return [user]
        if opts.get("all_active"):
            qs = qs.filter(is_staff=False)
            qs = qs.filter(profile__onboarding_completed=True)
        else:
            # Default: only the staff superuser to keep accidental runs quiet.
            qs = qs.filter(is_staff=True)
        if opts.get("level"):
            qs = qs.filter(profile__cefr_level=opts["level"].upper())
        return list(qs.distinct().order_by("id"))
