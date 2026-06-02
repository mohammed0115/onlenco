"""Prompt 16.5 — recompute estimated cost for image (media_generation) usage
logs that were recorded with $0 before per-image pricing existed.

    python manage.py reconcile_image_ai_usage_costs --dry-run
    python manage.py reconcile_image_ai_usage_costs --confirm

Only touches feature=media_generation logs whose cost is 0 AND for which an
image price now exists. Never touches text/audio logs. Preserves metadata.
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from ai_usage.services import cost_calculator as cc


class Command(BaseCommand):
    help = "Reconcile $0 image-generation usage costs using new image pricing."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        qs = AIUsageLog.objects.filter(
            feature=C.FEATURE_MEDIA_GENERATION, estimated_cost_usd=Decimal("0"))
        updated = skipped = 0
        for log in qs:
            n = int((log.metadata or {}).get("image_count", 1) or 1)
            new_cost = cc.calculate_image_cost(log.provider, log.model_name, n)
            if new_cost <= 0:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"  log#{log.id} {log.model_name}: no image price → left at $0."))
                continue
            self.stdout.write(
                f"  log#{log.id} {log.model_name} x{n}: $0 → ${new_cost}"
                + ("" if not dry_run else "  [DRY]"))
            if not dry_run:
                md = dict(log.metadata or {})
                md["image_cost_recalculated_after_prompt_16_5"] = True
                md["image_cost_original_usd"] = "0"
                log.estimated_cost_usd = new_cost
                log.metadata = md
                log.save(update_fields=["estimated_cost_usd", "metadata"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"\n[{'DRY-RUN' if dry_run else 'DONE'}] reconciled={updated} skipped={skipped} "
            f"(only feature=media_generation with $0 cost; text/audio untouched)."))
