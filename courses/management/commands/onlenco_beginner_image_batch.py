"""Batch image generation for the Onlenco Beginner course (Prompt 07).

Iterates `LessonImagePrompt` rows that aren't yet generated, calls
DALL-E 3 via `courses.services.onlenco_media_clients.generate_image`,
and saves the resulting PNG onto the model's `generated_image` field.

Idempotency: rows with `is_generated=True` are skipped by default. Pass
`--regenerate` to force re-generation.

Selection flags (mirror the spec):
  --unit N                  → only generate for Lesson order==N
  --range FROM-TO           → generate for orders in the inclusive range
  --all                     → every unit (default)
  --prompt-type cover       → only the cover prompt (default; cheapest)
  --prompt-type all         → all 4 prompt types per Lesson (~$7.68 for 192)
  --dry-run                 → print plan + cost estimate, write nothing
  --regenerate              → re-roll already-generated rows
"""
from __future__ import annotations

import logging

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, LessonImagePrompt
from courses.services.onlenco_media_clients import generate_image


COURSE_SLUG = "onlenco-beginner"
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate Beginner-pack images via DALL-E 3 and persist them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course-slug", default=COURSE_SLUG,
            help=f"Course slug (default: {COURSE_SLUG}).",
        )
        parser.add_argument("--unit", type=int, default=None,
                            help="Single Lesson order (1..48).")
        parser.add_argument("--range", dest="range_", default=None,
                            help="Inclusive 'FROM-TO' (e.g. 1-8).")
        parser.add_argument("--all", action="store_true",
                            help="Every unit (default if no --unit/--range).")
        parser.add_argument("--prompt-type", default="cover",
                            choices=["cover", "vocabulary", "grammar", "quiz", "all"],
                            help="Which prompt_type(s) to generate.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show the plan + cost estimate, write nothing.")
        parser.add_argument("--regenerate", action="store_true",
                            help="Re-generate even rows already marked is_generated.")

    def handle(self, *args, **options):
        slug = options["course_slug"]
        try:
            course = Course.objects.get(slug=slug)
        except Course.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                f"Course '{slug}' not found — run the matching seed command first."
            ))
            return

        qs = LessonImagePrompt.objects.filter(lesson__course=course)
        qs = self._filter_by_units(qs, options)
        if options["prompt_type"] != "all":
            qs = qs.filter(prompt_type=options["prompt_type"])
        if not options["regenerate"]:
            qs = qs.filter(is_generated=False)
        qs = qs.order_by("lesson__order", "sort_order").select_related("lesson")

        n = qs.count()
        est_cost = n * 0.04
        self.stdout.write(
            f"Plan: {n} image(s) to generate (~${est_cost:.2f} at DALL-E 3 standard)."
        )

        if options["dry_run"]:
            for ip in qs[:5]:
                self.stdout.write(f"  would generate: L{ip.lesson.order:02d} {ip.prompt_type}")
            if n > 5:
                self.stdout.write(f"  ... and {n - 5} more")
            self.stdout.write(self.style.WARNING("DRY RUN — no API calls made."))
            return

        if n == 0:
            self.stdout.write("Nothing to do.")
            return

        ok_count = 0
        fail_count = 0
        actual_cost = 0.0

        for ip in qs:
            self.stdout.write(
                f"  L{ip.lesson.order:02d} {ip.prompt_type} → calling DALL-E...",
                ending=" ",
            )
            self.stdout.flush()
            result = generate_image(ip.prompt)
            if not result.ok:
                fail_count += 1
                self.stdout.write(self.style.ERROR(f"FAIL: {result.error}"))
                continue

            with transaction.atomic():
                filename = f"unit{ip.lesson.order:02d}_{ip.prompt_type}.png"
                ip.generated_image.save(filename, ContentFile(result.bytes_), save=False)
                ip.is_generated = True
                ip.save(update_fields=["generated_image", "is_generated", "updated_at"])
            ok_count += 1
            actual_cost += result.cost_estimate_usd
            self.stdout.write(self.style.SUCCESS(f"OK (${result.cost_estimate_usd:.3f})"))

        self.stdout.write(self.style.SUCCESS(
            f"Done — {ok_count} generated, {fail_count} failed. "
            f"Approx spend: ${actual_cost:.2f}."
        ))

    def _filter_by_units(self, qs, options):
        if options["unit"]:
            return qs.filter(lesson__order=options["unit"])
        if options["range_"]:
            try:
                lo, hi = [int(x) for x in options["range_"].split("-", 1)]
                return qs.filter(lesson__order__gte=lo, lesson__order__lte=hi)
            except Exception:
                self.stderr.write(self.style.ERROR(
                    f"Invalid --range {options['range_']!r}; use 'FROM-TO' (e.g. 1-8)."
                ))
                return qs.none()
        return qs   # --all (default)
