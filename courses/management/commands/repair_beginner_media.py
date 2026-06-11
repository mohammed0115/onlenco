"""Safe, limited media repair for the Beginner course (Prompt 18.2C).

This command DRY-RUNS by default and only ever APPROVES media that already has
a real file on disk and belongs to one of the canonical 48 lessons. It NEVER
generates, deletes, or relinks media, and never touches progress or quizzes.

Scope (opt-in via flags):
  * --include-audio          approve LessonAudioScript rows that have a file
  * --include-cover-images   approve LessonImagePrompt rows that have a file
  * --include-missing-illustrations  PLAN ONLY — counts the 144 missing
                             illustrations; never generates them here.

Approval = generation_status -> "approved" (+ reviewed_at), which is exactly
what ``is_student_visible`` needs (approved AND file present). Idempotent.
No migrations, no schema changes.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from courses.models import (
    Course, Lesson, LessonAudioScript, LessonImagePrompt,
)

_DEFAULT_SLUG = "onlenco-beginner"
_EXPECTED = 48
_COVER_TYPE = "cover"


def _file_on_disk(filefield) -> bool:
    if not filefield:
        return False
    try:
        return filefield.storage.exists(filefield.name)
    except Exception:
        return False


class Command(BaseCommand):
    help = (
        "Safely APPROVE existing Beginner media that already has a file on disk "
        "(DRY-RUN by default). Never generates, deletes, or relinks media."
    )

    def add_arguments(self, parser):
        parser.add_argument("--course-slug", default=_DEFAULT_SLUG)
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--apply", action="store_true",
                            help="Actually approve (overrides the default dry-run).")
        parser.add_argument("--approve-existing", action="store_true",
                            help="Approve only media that already has a valid file.")
        parser.add_argument("--include-audio", action="store_true")
        parser.add_argument("--include-cover-images", action="store_true")
        parser.add_argument("--include-missing-illustrations", action="store_true",
                            help="PLAN ONLY — count missing illustrations; never generate here.")
        parser.add_argument("--format", choices=["text", "json"], default="text")

    def handle(self, *args, **options):
        apply = options["apply"]
        slug = options["course_slug"]
        course = Course.objects.filter(slug=slug).first()
        if course is None:
            raise CommandError(f"Course not found: {slug!r}")

        canonical = list(
            Lesson.objects.filter(
                course=course, book_unit_number__gte=1, book_unit_number__lte=_EXPECTED,
            ).order_by("book_unit_number")
        )
        canonical_ids = {le.pk for le in canonical}
        if len(canonical) != _EXPECTED:
            raise CommandError(
                f"Refusing to repair: expected {_EXPECTED} canonical lessons, "
                f"found {len(canonical)} (book_unit_number 1..48)."
            )

        approve_existing = options["approve_existing"]
        want_audio = options["include_audio"]
        want_cover = options["include_cover_images"]

        audio_to_approve, audio_skipped_no_file, audio_already = [], 0, 0
        if want_audio and approve_existing:
            for s in LessonAudioScript.objects.filter(lesson_id__in=canonical_ids):
                if not (s.generated_audio and _file_on_disk(s.generated_audio)):
                    audio_skipped_no_file += 1
                    continue
                if s.generation_status == "approved":
                    audio_already += 1
                    continue
                audio_to_approve.append(s)

        cover_to_approve, cover_skipped_no_file, cover_already = [], 0, 0
        if want_cover and approve_existing:
            for p in LessonImagePrompt.objects.filter(
                lesson_id__in=canonical_ids, prompt_type=_COVER_TYPE
            ):
                if not (p.generated_image and _file_on_disk(p.generated_image)):
                    cover_skipped_no_file += 1
                    continue
                if p.generation_status == "approved":
                    cover_already += 1
                    continue
                cover_to_approve.append(p)

        # Missing illustrations are PLANNED only — never generated here.
        missing_illustrations = (
            LessonImagePrompt.objects
            .filter(lesson_id__in=canonical_ids)
            .exclude(prompt_type=_COVER_TYPE)
            .filter(generated_image="")
            .count()
        )

        report = {
            "course_slug": slug,
            "applied": apply,
            "canonical_lessons": len(canonical),
            "planned_audio_approvals": len(audio_to_approve),
            "planned_cover_image_approvals": len(cover_to_approve),
            "audio_already_approved": audio_already,
            "cover_already_approved": cover_already,
            "audio_skipped_no_file": audio_skipped_no_file,
            "cover_skipped_no_file": cover_skipped_no_file,
            "missing_illustrations_plan_only": missing_illustrations,
        }

        if not apply:
            report["note"] = "DRY-RUN — no changes written. Re-run with --apply."
            self._emit(report, options["format"])
            return

        now = timezone.now()
        with transaction.atomic():
            approved_audio = 0
            for s in audio_to_approve:
                if not _file_on_disk(s.generated_audio):
                    continue  # re-check inside the transaction
                s.generation_status = "approved"
                s.reviewed_at = now
                s.save(update_fields=["generation_status", "reviewed_at", "updated_at"])
                approved_audio += 1
            approved_cover = 0
            for p in cover_to_approve:
                if not _file_on_disk(p.generated_image):
                    continue
                p.generation_status = "approved"
                p.reviewed_at = now
                p.save(update_fields=["generation_status", "reviewed_at", "updated_at"])
                approved_cover += 1
        report.update({
            "approved_audio": approved_audio,
            "approved_cover_images": approved_cover,
            "regeneration_performed": False,
        })
        self._emit(report, options["format"])

    def _emit(self, report, fmt):
        if fmt == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return
        w = self.stdout.write
        w("=" * 72)
        w("Beginner media repair " + ("(APPLIED)" if report["applied"] else "(DRY-RUN)"))
        w("=" * 72)
        w(f"Course: {report['course_slug']}  canonical_lessons={report['canonical_lessons']}")
        w(f"Planned audio approvals       : {report['planned_audio_approvals']}")
        w(f"Planned cover-image approvals : {report['planned_cover_image_approvals']}")
        w(f"Already approved (audio/cover) : {report['audio_already_approved']}/{report['cover_already_approved']}")
        w(f"Skipped — no file (audio/cover): {report['audio_skipped_no_file']}/{report['cover_skipped_no_file']}")
        w(f"Missing illustrations (PLAN ONLY, not generated): {report['missing_illustrations_plan_only']}")
        if report["applied"]:
            w(f"Approved audio: {report.get('approved_audio')}  "
              f"Approved cover images: {report.get('approved_cover_images')}  "
              f"regeneration_performed={report.get('regeneration_performed')}")
        else:
            w(report.get("note", ""))
