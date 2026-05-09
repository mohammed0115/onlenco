"""Bulk-approve `GeneratedQuestion` rows for training.

Defaults are conservative: only items that are already
  * `is_active=True`
  * `is_reviewed=True`
  * `quality_score >= --min-quality` (default 80)
are flipped to `approved_for_training=True`.

Use --dry-run to see the count first.

Examples
--------
    python manage.py approve_questions_for_training --dry-run
    python manage.py approve_questions_for_training --min-quality 70
    python manage.py approve_questions_for_training --cefr-level B1 --skill grammar
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from question_factory.models import GeneratedQuestion


class Command(BaseCommand):
    help = "Mark high-quality GeneratedQuestion rows as approved for training."

    def add_arguments(self, parser):
        parser.add_argument("--min-quality", type=int, default=80,
                            help="Minimum quality_score required (default 80).")
        parser.add_argument("--cefr-level", type=str, default="")
        parser.add_argument("--skill", type=str, default="")
        parser.add_argument("--include-unreviewed", action="store_true",
                            default=False,
                            help="Approve even items that have not been reviewed yet.")
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--limit", type=int, default=0,
                            help="Cap the number of rows updated (0 = all).")

    def handle(self, *args, **opts):
        qs = GeneratedQuestion.objects.filter(
            is_active=True,
            quality_score__gte=opts["min_quality"],
            approved_for_training=False,
        )
        if not opts["include_unreviewed"]:
            qs = qs.filter(is_reviewed=True)
        if opts["cefr_level"]:
            qs = qs.filter(cefr_level=opts["cefr_level"])
        if opts["skill"]:
            qs = qs.filter(skill=opts["skill"])

        eligible = qs.count()
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        if opts["dry_run"]:
            self.stdout.write(self.style.NOTICE(
                f"[dry-run] would approve {eligible} item(s) "
                f"(filters: cefr={opts['cefr_level'] or 'ALL'} "
                f"skill={opts['skill'] or 'ALL'} "
                f"min_quality={opts['min_quality']})."
            ))
            return

        # Bulk update is much faster than per-row save.
        if opts["limit"]:
            ids = list(qs.values_list("id", flat=True))
            n = GeneratedQuestion.objects.filter(id__in=ids).update(
                approved_for_training=True,
            )
        else:
            n = qs.update(approved_for_training=True)

        self.stdout.write(self.style.SUCCESS(
            f"approved {n} item(s) for training "
            f"(eligible_pool={eligible})."
        ))
