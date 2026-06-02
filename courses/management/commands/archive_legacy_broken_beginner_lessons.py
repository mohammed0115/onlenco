"""Prompt 12B.1 — archive legacy broken PUBLISHED lessons in onlenco-beginner.

These are old/legacy lessons that are `published` (student-visible) but score
0 / fail the quality checker. They predate the review workflow and must be
hidden BEFORE any approval batch. We DO NOT delete them, DO NOT touch Topic 01
(Gold Reference), and DO NOT touch the new pending_review Topics 02-48.

    python manage.py archive_legacy_broken_beginner_lessons --dry-run
    python manage.py archive_legacy_broken_beginner_lessons --confirm
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Lesson, LessonReviewEvent
from courses.services import content_quality_checker as q

COURSE_SLUG = "onlenco-beginner"
GOLD_TITLE = "Introducing Yourself"
BROKEN_SCORE_THRESHOLD = 70  # below this AND published AND not gold => legacy broken
ARCHIVE_NOTE = (
    "Archived by Prompt 12B.1 because this is a legacy broken lesson scoring 0 "
    "and was student-visible before approval workflow."
)


def find_legacy_broken():
    """Published, non-gold lessons in onlenco-beginner that fail the checker."""
    out = []
    qs = Lesson.objects.filter(course__slug=COURSE_SLUG, status="published")
    for L in qs.order_by("order", "id"):
        # Never the Gold Reference.
        if L.order == 1 or L.title == GOLD_TITLE:
            continue
        score = q.check_lesson_quality(L)["score"]
        if score < BROKEN_SCORE_THRESHOLD:
            out.append((L, score))
    return out


class Command(BaseCommand):
    help = "Archive legacy broken published lessons in the onlenco-beginner course."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true", dest="confirm")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        found = find_legacy_broken()

        self.stdout.write(f"Found {len(found)} legacy broken published lesson(s):")
        warnings = []
        for L, score in found:
            self.stdout.write(
                f"  id={L.id} order={L.order} score={score} status={L.status} | {L.title}"
            )
            if getattr(L, "challenge_sessions", None) and L.challenge_sessions.exists():
                warnings.append(f"id={L.id} has student attempts — preserved (not deleted).")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "[DRY-RUN] No changes written. Re-run with --confirm to archive."))
            for w in warnings:
                self.stdout.write(self.style.WARNING("  WARN: " + w))
            return

        archived = 0
        with transaction.atomic():
            for L, score in found:
                old = L.status
                L.status = "archived"
                L.is_active = False
                L.save(update_fields=["status", "is_active", "updated_at"])
                LessonReviewEvent.objects.create(
                    lesson=L, actor=None, action="archive",
                    from_status=old, to_status="archived",
                    quality_score=score, note=ARCHIVE_NOTE,
                    metadata={"phase": "12b1", "reason": "legacy_broken_published",
                              "old_status": old},
                )
                archived += 1

        self.stdout.write(self.style.SUCCESS(
            f"Archived {archived} legacy broken lesson(s) → status='archived' (hidden from students)."))
        for w in warnings:
            self.stdout.write(self.style.WARNING("  WARN: " + w))
