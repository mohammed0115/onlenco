"""Bulk-approve generated lesson media that already has a file but is still
pending review, so approved students can see/hear it.

    python manage.py approve_media_with_files --dry-run
    python manage.py approve_media_with_files --confirm

Approves every LessonAudioScript / LessonImagePrompt that HAS a generated
file and whose status is NOT already approved or rejected. Rejected items are
left alone (they were rejected on purpose). Idempotent — a second run approves
nothing new. Touches only the review fields (status + reviewed_at); never the
lesson/course status.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import LessonAudioScript, LessonImagePrompt

SKIP_STATUSES = ["approved", "rejected"]


class Command(BaseCommand):
    help = "Approve generated media that has a file but isn't approved yet (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", dest="dry_run")
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"] or not opts["confirm"]
        now = timezone.now()

        audio_qs = (
            LessonAudioScript.objects.exclude(generated_audio="")
            .exclude(generation_status__in=SKIP_STATUSES)
        )
        image_qs = (
            LessonImagePrompt.objects.exclude(generated_image="")
            .exclude(generation_status__in=SKIP_STATUSES)
        )
        audio_n = audio_qs.count()
        image_n = image_qs.count()

        if not dry_run:
            audio_qs.update(generation_status="approved", reviewed_at=now)
            image_qs.update(generation_status="approved", reviewed_at=now)

        self.stdout.write(self.style.SUCCESS(
            f"[{'DRY-RUN' if dry_run else 'DONE'}] "
            f"audio {'would be ' if dry_run else ''}approved={audio_n}  "
            f"image {'would be ' if dry_run else ''}approved={image_n}  "
            f"(items with a file, not previously approved/rejected; lesson status untouched)."
        ))
