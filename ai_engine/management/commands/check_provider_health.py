"""Drift / health check for the model router.

Reads the last `--days` of `ModelPredictionLog`, computes the success
rate per `(task_type, provider)`, and flags any pair below
`--min-success-rate`. Exits with non-zero status when anything is
flagged so cron can alert.

Examples
--------
    # Default: last 7 days, threshold 0.80
    python manage.py check_provider_health

    # Tighter threshold + JSON output for an alerting pipeline
    python manage.py check_provider_health --days 1 --min-success-rate 0.95 --json

    # Auto-disable any provider that fails the threshold
    python manage.py check_provider_health --auto-disable
"""
from __future__ import annotations

import json
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from ai_engine.models import ModelPredictionLog, ProviderKillSwitch


class Command(BaseCommand):
    help = "Compute per-provider success rates over a recent window."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--min-success-rate", type=float, default=0.80)
        parser.add_argument("--min-samples", type=int, default=10,
                            help="Skip pairs with fewer than N samples (avoid noise).")
        parser.add_argument("--auto-disable", action="store_true", default=False,
                            help="Add a ProviderKillSwitch row for any flagged pair.")
        parser.add_argument("--json", action="store_true", default=False)

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(days=opts["days"])
        rows = (
            ModelPredictionLog.objects
            .filter(created_at__gte=cutoff)
            .values("task_type", "provider")
            .annotate(
                total=Count("id"),
                ok=Count("id", filter=Q(success=True)),
            )
        )

        report = []
        flagged = []
        for r in rows:
            total = r["total"] or 0
            ok = r["ok"] or 0
            rate = (ok / total) if total else 0.0
            entry = {
                "task_type": r["task_type"],
                "provider": r["provider"],
                "samples": total,
                "success_rate": round(rate, 3),
            }
            if total < opts["min_samples"]:
                entry["status"] = "low_sample"
            elif rate < opts["min_success_rate"]:
                entry["status"] = "FLAGGED"
                flagged.append(entry)
            else:
                entry["status"] = "ok"
            report.append(entry)

        if opts["auto_disable"] and flagged:
            for f in flagged:
                ProviderKillSwitch.objects.update_or_create(
                    task_type=f["task_type"], provider=f["provider"],
                    defaults={
                        "disabled": True,
                        "reason": (f"auto-disabled: {f['samples']} samples, "
                                   f"success={f['success_rate']} "
                                   f"< {opts['min_success_rate']}"),
                    },
                )

        if opts["json"]:
            self.stdout.write(json.dumps({
                "cutoff": cutoff.isoformat(),
                "min_success_rate": opts["min_success_rate"],
                "flagged": flagged,
                "report": report,
            }, indent=2))
        else:
            self.stdout.write(self.style.NOTICE(
                f"Window: last {opts['days']}d (cutoff {cutoff.isoformat()})"
            ))
            for entry in report:
                style = (self.style.ERROR if entry["status"] == "FLAGGED"
                         else self.style.SUCCESS if entry["status"] == "ok"
                         else self.style.NOTICE)
                self.stdout.write(style(
                    f"  {entry['task_type']:24} {entry['provider']:18} "
                    f"samples={entry['samples']:>5} "
                    f"rate={entry['success_rate']:.3f}  [{entry['status']}]"
                ))
            if flagged:
                self.stdout.write(self.style.ERROR(
                    f"\n{len(flagged)} provider(s) below threshold."
                ))
                if opts["auto_disable"]:
                    self.stdout.write(self.style.WARNING(
                        "Auto-disabled via ProviderKillSwitch rows."
                    ))

        if flagged:
            sys.exit(1)
