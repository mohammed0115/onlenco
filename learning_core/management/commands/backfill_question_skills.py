"""Backfill `LessonQuestion.metadata['skills']` from the lesson's
grammar_topic / vocabulary_topic when not already set.

Dry-run by default. Pass `--confirm` to actually write.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from courses.models import LessonQuestion
from learning_core.models import Skill


class Command(BaseCommand):
    help = "Backfill skill metadata on LessonQuestion rows. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm", action="store_true",
            help="Actually write — defaults to dry-run.",
        )
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Cap how many rows to scan (0 = all).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        skill_codes = set(
            Skill.objects.filter(is_active=True).values_list("code", flat=True)
        )
        skill_codes.discard(None)

        qs = (
            LessonQuestion.objects
            .select_related("quiz__lesson")
            .order_by("pk")
        )
        if options["limit"]:
            qs = qs[: options["limit"]]

        scanned, updated, skipped = 0, 0, 0
        for q in qs.iterator():
            scanned += 1
            md = q.metadata or {}
            if md.get("skills") or md.get("skill"):
                skipped += 1
                continue
            lesson = getattr(q.quiz, "lesson", None)
            if lesson is None:
                continue
            for attr in ("grammar_topic", "vocabulary_topic"):
                raw = (getattr(lesson, attr, "") or "").strip()
                if not raw:
                    continue
                candidate = slugify(raw).replace("-", "_")
                if candidate in skill_codes:
                    if options["confirm"]:
                        md["skills"] = [candidate]
                        q.metadata = md
                        q.save(update_fields=["metadata"])
                    updated += 1
                    break

        mode = "WROTE" if options["confirm"] else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] scanned={scanned} updated={updated} skipped={skipped}"
        ))
        if not options["confirm"]:
            self.stdout.write("Pass --confirm to actually write the metadata.")
