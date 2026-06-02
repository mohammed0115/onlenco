"""Aggregate AIUsageLog → AIDailyUsageSummary.

    python manage.py aggregate_ai_usage_daily --date=YYYY-MM-DD
    python manage.py aggregate_ai_usage_daily --from-date=... --to-date=...
"""
from __future__ import annotations

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...services import aggregation


def _d(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


class Command(BaseCommand):
    help = "Aggregate AI usage logs into daily summaries."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default=None)
        parser.add_argument("--from-date", type=str, default=None, dest="from_date")
        parser.add_argument("--to-date", type=str, default=None, dest="to_date")
        parser.add_argument("--user", type=int, default=None)
        parser.add_argument("--organization", type=str, default=None)
        parser.add_argument("--force", action="store_true",
                            help="Recalculate (delete + rebuild) instead of upsert.")

    def handle(self, *args, **opts):
        if opts["from_date"] and opts["to_date"]:
            date_from, date_to = _d(opts["from_date"]), _d(opts["to_date"])
        else:
            day = _d(opts["date"]) if opts["date"] else (timezone.localdate() - timedelta(days=1))
            date_from = date_to = day

        total = 0
        cur = date_from
        while cur <= date_to:
            if opts["force"]:
                total += aggregation.recalculate_day(cur)
            else:
                total += aggregation.aggregate_day(cur)
            cur += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f"Aggregated {date_from}..{date_to}: {total} summary rows."
        ))
