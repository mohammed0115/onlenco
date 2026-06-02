"""Prompt 15 — cleanup/rollback for the media pilot.

Hides generated media by marking it rejected (default) — never hard-deletes
approved media, never deletes AIUsageLog history. File deletion requires an
explicit --delete-files.

    python manage.py cleanup_generated_media_batch --course=onlenco-beginner --topics=2-6 --dry-run
    python manage.py cleanup_generated_media_batch --course=onlenco-beginner --topics=2-6 --confirm --only-status=needs_review [--delete-files]
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import Lesson, LessonAudioScript, LessonImagePrompt


def _parse_topics(spec: str) -> list[int]:
    spec = (spec or "").strip()
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in spec.split(",") if x.strip()]


class Command(BaseCommand):
    help = "Cleanup generated media for Batch-1 topics (mark rejected; never delete approved)."

    def add_arguments(self, parser):
        parser.add_argument("--course", required=True)
        parser.add_argument("--topics", required=True)
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--only-status", dest="only_status", default="needs_review")
        parser.add_argument("--delete-files", action="store_true", dest="delete_files")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        orders = _parse_topics(opts["topics"])
        only = opts["only_status"]
        lessons = (Lesson.objects.filter(course__slug=opts["course"], order__in=orders)
                   .exclude(status="archived"))

        affected = 0
        for Model, file_attr in ((LessonImagePrompt, "generated_image"),
                                 (LessonAudioScript, "generated_audio")):
            qs = Model.objects.filter(lesson__in=lessons, generation_status=only)
            # Safety: never touch approved media here.
            qs = qs.exclude(generation_status="approved")
            for obj in qs:
                affected += 1
                if dry_run:
                    self.stdout.write(f"  [DRY] would reject {Model.__name__}#{obj.id} "
                                      f"(T{obj.lesson.order:02d} {only})")
                    continue
                obj.generation_status = "rejected"
                obj.review_notes = (obj.review_notes + " | cleaned up by cleanup_generated_media_batch").strip(" |")
                obj.reviewed_at = timezone.now()
                fields = ["generation_status", "review_notes", "reviewed_at", "updated_at"]
                if opts["delete_files"]:
                    f = getattr(obj, file_attr)
                    if f:
                        f.delete(save=False)
                    obj.is_generated = False
                    fields += [file_attr, "is_generated"]
                obj.save(update_fields=fields)
                self.stdout.write(f"  rejected {Model.__name__}#{obj.id} (T{obj.lesson.order:02d})")

        self.stdout.write(self.style.SUCCESS(
            f"\n[{'DRY-RUN' if dry_run else 'DONE'}] affected={affected} "
            f"(approved media untouched; AIUsageLog history preserved)."))
