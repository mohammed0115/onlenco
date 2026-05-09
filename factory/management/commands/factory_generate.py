"""Render templates × banks → validate → promote into AdaptiveExercise.

Examples:
    python manage.py factory_generate --target-count 100000 --batch-size 500
    python manage.py factory_generate --topic-kind grammar --cefr A1 --target-count 5000
    python manage.py factory_generate --template-code tpl-grammar-A1-presimple-3sg --target-count 2000
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from factory.models import QuestionTemplate
from factory.services import promotion_service
from factory.services.template_engine import render_many


class Command(BaseCommand):
    help = "Generate questions via templates+banks and promote them."

    def add_arguments(self, parser):
        parser.add_argument("--target-count", type=int, default=10_000)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--topic-kind", type=str, default="")
        parser.add_argument("--cefr", type=str, default="")
        parser.add_argument("--template-code", type=str, default="")
        parser.add_argument("--allow-ai-validation", action="store_true", default=False)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **opts):
        target = opts["target_count"]
        batch = opts["batch_size"]
        templates = QuestionTemplate.objects.filter(is_active=True).select_related("topic")
        if opts["template_code"]:
            templates = templates.filter(code=opts["template_code"])
        if opts["topic_kind"]:
            templates = templates.filter(topic__kind=opts["topic_kind"])
        if opts["cefr"]:
            templates = templates.filter(cefr_level=opts["cefr"])
        templates = list(templates)
        if not templates:
            self.stdout.write(self.style.ERROR("No matching templates."))
            return

        self.stdout.write(self.style.NOTICE(
            f"target={target:,} batch={batch} templates={len(templates)} "
            f"ai={opts['allow_ai_validation']} dry_run={opts['dry_run']}"
        ))

        totals = {"candidates": 0, "approved": 0, "rejected": 0,
                  "duplicates": 0, "written": 0}
        t0 = time.time()
        variant = 0
        while totals["written"] < target:
            progressed = False
            for tpl in templates:
                if totals["written"] >= target:
                    break
                # Cap one chunk at min(batch, remaining-target).
                this_chunk = min(batch, target - totals["written"])
                items = render_many(tpl, count=this_chunk, start_variant=variant)
                if opts["dry_run"]:
                    totals["candidates"] += len(items)
                    self.stdout.write(
                        f"  [DRY] tpl={tpl.code} v={variant} "
                        f"+{len(items)} (total candidates {totals['candidates']:,})"
                    )
                    progressed = True
                    continue
                stats = promotion_service.promote(
                    items, allow_ai_validation=opts["allow_ai_validation"],
                )
                for k in totals:
                    totals[k] += stats.get(k, 0)
                self.stdout.write(
                    f"  tpl={tpl.code} v={variant} +{stats['written']} "
                    f"approved={stats['approved']} rej={stats['rejected']} "
                    f"dups={stats['duplicates']}  total={totals['written']:,}/{target:,}"
                )
                if stats["written"] > 0:
                    progressed = True
            variant += 1
            if not progressed:
                self.stdout.write(self.style.WARNING(
                    "No new items rendered — template space exhausted "
                    "(all candidates duplicates or rejected)."
                ))
                break
        secs = time.time() - t0
        self.stdout.write(self.style.SUCCESS(
            f"done in {secs:.1f}s — written={totals['written']:,} "
            f"approved={totals['approved']:,} rejected={totals['rejected']:,} "
            f"duplicates={totals['duplicates']:,}"
        ))
