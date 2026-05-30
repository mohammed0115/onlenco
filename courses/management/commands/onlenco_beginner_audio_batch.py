"""Batch audio generation for the Onlenco Beginner course (Prompt 08).

Iterates `LessonAudioScript` rows that aren't yet generated, runs each
script through `clean_script_for_tts` (strips HTML, underscores,
placeholders), calls OpenAI TTS via
`courses.services.onlenco_media_clients.generate_audio`, and persists
the MP3 onto `generated_audio`.

Selection flags mirror the image batch command:
  --unit N            → only generate for Lesson order==N
  --range FROM-TO     → inclusive
  --all               → every unit (default)
  --script-type X     → restrict to one script_type (default: all 6)
  --dry-run           → print plan + cost estimate, no API calls
  --regenerate        → re-roll already-generated rows
"""
from __future__ import annotations

import logging

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import (
    Course, LessonAudioScript, LESSON_AUDIO_SCRIPT_TYPE_CHOICES,
)
from courses.services.onlenco_media_clients import (
    clean_script_for_tts, generate_audio,
)


COURSE_SLUG = "onlenco-beginner"
logger = logging.getLogger(__name__)

VALID_SCRIPT_TYPES = [c[0] for c in LESSON_AUDIO_SCRIPT_TYPE_CHOICES]


class Command(BaseCommand):
    help = "Generate Beginner-pack audio via OpenAI TTS and persist it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course-slug", default=COURSE_SLUG,
            help=f"Course slug (default: {COURSE_SLUG}).",
        )
        parser.add_argument("--unit", type=int, default=None)
        parser.add_argument("--range", dest="range_", default=None)
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--script-type", default="all",
                            choices=["all"] + VALID_SCRIPT_TYPES)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--regenerate", action="store_true")

    def handle(self, *args, **options):
        slug = options["course_slug"]
        try:
            course = Course.objects.get(slug=slug)
        except Course.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                f"Course '{slug}' not found — run the matching seed command first."
            ))
            return

        qs = LessonAudioScript.objects.filter(lesson__course=course)
        qs = self._filter_by_units(qs, options)
        if options["script_type"] != "all":
            qs = qs.filter(script_type=options["script_type"])
        if not options["regenerate"]:
            qs = qs.filter(is_generated=False)
        qs = qs.order_by("lesson__order", "sort_order").select_related("lesson")

        n = qs.count()
        # Rough cost estimate from the lengths we'll actually send.
        total_chars = sum(
            len(clean_script_for_tts(s.script_text)) for s in qs[:200]
        )
        # Scale up if there are more rows than the sample.
        if n > 200:
            total_chars = int(total_chars * (n / 200))
        est_cost = total_chars * 15.0 / 1_000_000
        self.stdout.write(
            f"Plan: {n} audio clip(s) (~{total_chars} chars, "
            f"≈${est_cost:.2f} at TTS-1)."
        )

        if options["dry_run"]:
            for s in qs[:5]:
                cleaned = clean_script_for_tts(s.script_text)
                self.stdout.write(
                    f"  would generate: L{s.lesson.order:02d} {s.script_type} "
                    f"({len(cleaned)} chars) → '{cleaned[:60]}...'"
                )
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

        for s in qs:
            cleaned = clean_script_for_tts(s.script_text)
            if not cleaned:
                fail_count += 1
                self.stdout.write(self.style.WARNING(
                    f"  L{s.lesson.order:02d} {s.script_type} — empty after cleaning, skipped"
                ))
                continue

            self.stdout.write(
                f"  L{s.lesson.order:02d} {s.script_type} "
                f"({len(cleaned)} chars) → TTS...",
                ending=" ",
            )
            self.stdout.flush()

            result = generate_audio(cleaned, voice_style=s.voice_style)
            if not result.ok:
                fail_count += 1
                self.stdout.write(self.style.ERROR(f"FAIL: {result.error}"))
                continue

            with transaction.atomic():
                filename = f"unit{s.lesson.order:02d}_{s.script_type}.mp3"
                s.generated_audio.save(filename, ContentFile(result.bytes_), save=False)
                s.is_generated = True
                s.save(update_fields=["generated_audio", "is_generated", "updated_at"])

            ok_count += 1
            actual_cost += result.cost_estimate_usd
            self.stdout.write(self.style.SUCCESS(
                f"OK (${result.cost_estimate_usd:.4f})"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"Done — {ok_count} generated, {fail_count} failed. "
            f"Approx spend: ${actual_cost:.3f}."
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
                    f"Invalid --range {options['range_']!r}; use 'FROM-TO'."
                ))
                return qs.none()
        return qs
