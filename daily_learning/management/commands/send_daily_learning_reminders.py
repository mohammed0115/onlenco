"""Send daily-plan reminder notifications to active students.

Variants (decided per user):
  - default     → "Your Onlenco daily plan is ready. Start with just 10 minutes."
  - inactive    → "We missed you! One short lesson is enough to restart."
  - streak      → "You're on an N-day streak! Don't break it."

Each reminder fires via NotificationService.trigger() so it inherits
the existing preference + delivery pipeline. The command is
idempotent within a 1-hour dedup window enforced by the notifications
service.
"""
from __future__ import annotations

import datetime as dt
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from daily_learning.models import DailyLearningPlan

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send today's daily-plan reminder notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            help="ISO date (YYYY-MM-DD). Defaults to today.",
        )
        parser.add_argument(
            "--all-active", action="store_true",
            help="Send to every active student with a plan today.",
        )
        parser.add_argument(
            "--user-id", type=int,
            help="Send to a specific user id only.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Don't actually send — print intended recipients.",
        )

    def handle(self, *args, **opts):
        target_date = self._parse_date(opts.get("date"))
        users = self._select_users(opts)
        if not users:
            self.stdout.write(self.style.WARNING("No matching users."))
            return

        try:
            from notifications import constants as Nc
            from notifications.services.notification_service import NotificationService
        except Exception as e:
            raise CommandError(f"notifications app missing: {e}")
        notifier = NotificationService()

        sent, skipped = 0, 0
        for user in users:
            plan = DailyLearningPlan.objects.filter(user=user, date=target_date).first()
            if not plan:
                skipped += 1
                continue
            event_type, payload = self._pick_event(user, plan, target_date, Nc)
            if opts["dry_run"]:
                self.stdout.write(
                    f"  [DRY] {user.email or user.username} → {event_type}"
                )
                continue
            try:
                notifier.trigger(
                    event_type,
                    user=user,
                    payload=payload,
                    priority=Nc.PRIORITY_NORMAL,
                )
                sent += 1
            except Exception as e:
                logger.exception("reminder failed for user_id=%s", user.id)
                self.stderr.write(self.style.ERROR(
                    f"  ✗ {user.email or user.username}: {e}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"Done. {sent} sent, {skipped} skipped (no plan)."
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
        qs = User.objects.filter(is_active=True, is_staff=False)
        if opts.get("user_id"):
            user = qs.filter(id=opts["user_id"]).first()
            if not user:
                raise CommandError(f"No active user with id={opts['user_id']}")
            return [user]
        if opts.get("all_active"):
            qs = qs.filter(profile__onboarding_completed=True)
        else:
            return []
        return list(qs.distinct().order_by("id"))

    def _pick_event(self, user, plan, on_date, Nc):
        """Choose the right notification flavor."""
        # Streak-based: prefer the streak-milestone reminder for users
        # with active long streaks.
        streak = 0
        try:
            from motivation.services import streak_service
            streak = streak_service.get_current_streak(user, on_date)
            inactive = streak_service.get_inactive_days(user, on_date)
        except Exception:
            inactive = 0

        if inactive >= 3:
            return Nc.DAILY_PLAN_COMEBACK, {
                "date": on_date.isoformat(),
                "inactive_days": inactive,
                "plan_id": plan.id,
            }
        if streak >= 7:
            return Nc.DAILY_PLAN_STREAK_REMINDER, {
                "date": on_date.isoformat(),
                "streak_days": streak,
                "plan_id": plan.id,
            }
        # Default "your plan is ready"
        return Nc.DAILY_PLAN_READY, {
            "date": on_date.isoformat(),
            "plan_id": plan.id,
            "title": plan.title,
            "estimated_minutes": plan.estimated_minutes,
            "source": "daily_learning",
        }
