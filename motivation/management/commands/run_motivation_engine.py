"""Run the motivation engine for one user, all users, or weekly summary."""
from datetime import datetime, date as _date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from motivation.services import motivation_engine

User = get_user_model()


class Command(BaseCommand):
    help = "Run the motivation engine. Defaults to today, all active users."

    def add_arguments(self, parser):
        parser.add_argument("--user", type=str, help="username or email of one user")
        parser.add_argument("--date", type=str, help="ISO date YYYY-MM-DD (defaults to today)")
        parser.add_argument("--weekly", action="store_true", help="run weekly summary instead of daily")

    def _parse_date(self, raw):
        if not raw:
            return timezone.localdate()
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as e:
            raise CommandError(f"Invalid --date: {e}")

    def _resolve_user(self, ident):
        try:
            return User.objects.get(username=ident)
        except User.DoesNotExist:
            pass
        try:
            return User.objects.get(email__iexact=ident)
        except User.DoesNotExist:
            raise CommandError(f"No user matched '{ident}'")

    def handle(self, *args, **opts):
        target_date: _date = self._parse_date(opts.get("date"))
        weekly = opts.get("weekly")
        user_ident = opts.get("user")

        if user_ident:
            user = self._resolve_user(user_ident)
            if weekly:
                msg = motivation_engine.run_weekly_summary(user, target_date)
                self.stdout.write(self.style.SUCCESS(
                    f"Weekly summary for {user}: {'sent' if msg else 'skipped'}."
                ))
                return
            res = motivation_engine.run_for_user(user, target_date)
            self.stdout.write(self.style.SUCCESS(f"Engine ran for {user}: {res}"))
            return

        if weekly:
            count = 0
            for user in User.objects.filter(is_active=True).iterator():
                if motivation_engine.run_weekly_summary(user, target_date):
                    count += 1
            self.stdout.write(self.style.SUCCESS(f"Weekly summaries sent: {count}"))
            return

        summary = motivation_engine.run_for_all_users(target_date)
        self.stdout.write(self.style.SUCCESS(
            f"Engine ran: users={summary['users']} ok={summary['ok']} errors={summary['errors']}"
        ))
