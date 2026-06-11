"""Review & approve generated Beginner illustration images (Prompt 18.2E).

Lists the generated illustrations (default status ``needs_review``), can export a
human-review manifest, and — only with ``--approve`` (and NOT ``--dry-run``) —
approves the ones that pass the safety criteria. It NEVER generates, deletes,
touches covers/audio, or approves media without a real file / outside the
canonical 48 / outside the vocabulary|grammar|quiz types.

Approval flips ``generation_status`` to ``approved`` via the official
``mark_media_approved`` helper, which is exactly what ``is_student_visible``
needs (approved AND file present). Idempotent; atomic.
"""
from __future__ import annotations

import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.models import Course, Lesson, LessonImagePrompt
from courses.services.media_generation_service import (
    mark_media_approved, mark_media_rejected,
)

_DEFAULT_SLUG = "onlenco-beginner"
_EXPECTED = 48
_COVER_TYPE = "cover"
_ALLOWED_TYPES = ("vocabulary", "grammar", "quiz")
_APPROVABLE_STATUSES = ("needs_review", "generated")


def _file_on_disk(ff) -> bool:
    if not ff:
        return False
    try:
        return ff.storage.exists(ff.name)
    except Exception:
        return False


def _dimensions(ff):
    try:
        from PIL import Image
        ff.open("rb")
        try:
            with Image.open(ff) as im:
                return list(im.size)
        finally:
            ff.close()
    except Exception:
        return None


def _file_size(ff):
    try:
        return int(ff.size)
    except Exception:
        return None


class Command(BaseCommand):
    help = (
        "Review and (with --approve) approve generated Beginner illustrations. "
        "DRY-RUN by default. Never generates, deletes, or touches covers/audio."
    )

    def add_arguments(self, parser):
        parser.add_argument("--course-slug", default=_DEFAULT_SLUG)
        parser.add_argument("--status", default="needs_review")
        parser.add_argument("--from-book-unit", type=int, default=None)
        parser.add_argument("--to-book-unit", type=int, default=None)
        parser.add_argument("--book-unit", type=int, default=None)
        parser.add_argument("--types", default=",".join(_ALLOWED_TYPES))
        parser.add_argument("--format", choices=["text", "json"], default="text")
        parser.add_argument("--export-manifest", default=None,
                            help="Write a JSON review manifest to this path.")
        parser.add_argument("--approve", action="store_true")
        parser.add_argument("--reject", default="",
                            help="Comma-separated LessonImagePrompt IDs to reject.")
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--apply", action="store_true",
                            help="Execute --approve/--reject (overrides dry-run).")

    def handle(self, *args, **options):
        slug = options["course_slug"]
        course = Course.objects.filter(slug=slug).first()
        if course is None:
            raise CommandError(f"Course not found: {slug!r}")

        canonical = list(
            Lesson.objects.filter(
                course=course, book_unit_number__gte=1, book_unit_number__lte=_EXPECTED,
            )
        )
        if len(canonical) != _EXPECTED:
            raise CommandError(
                f"Refusing to review: expected {_EXPECTED} canonical lessons, "
                f"found {len(canonical)}."
            )
        canonical_ids = {le.pk for le in canonical}

        types = [t.strip() for t in (options["types"] or "").split(",") if t.strip()]
        types = [t for t in types if t in _ALLOWED_TYPES]  # cover never included
        if not types:
            raise CommandError(f"--types must be a subset of {_ALLOWED_TYPES}.")

        bu, frm, to = options["book_unit"], options["from_book_unit"], options["to_book_unit"]

        def in_range(n):
            if bu is not None and n != bu:
                return False
            if frm is not None and n < frm:
                return False
            if to is not None and n > to:
                return False
            return True

        prompts = list(
            LessonImagePrompt.objects
            .filter(lesson_id__in=canonical_ids, prompt_type__in=types,
                    generation_status=options["status"])
            .select_related("lesson")
            .order_by("lesson__book_unit_number", "prompt_type", "id")
        )
        prompts = [p for p in prompts if in_range(p.lesson.book_unit_number)]

        # Duplicate detection: more than one row for the same (lesson, type).
        seen = {}
        for p in prompts:
            seen.setdefault((p.lesson_id, p.prompt_type), []).append(p.id)
        dup_keys = {k for k, v in seen.items() if len(v) > 1}

        rows = []
        for p in prompts:
            ff = p.generated_image
            has_file = _file_on_disk(ff)
            is_dup = (p.lesson_id, p.prompt_type) in dup_keys
            eligible = (
                has_file
                and p.lesson_id in canonical_ids
                and p.prompt_type in types
                and p.prompt_type != _COVER_TYPE
                and p.generation_status in _APPROVABLE_STATUSES
                and not is_dup
            )
            rows.append({
                "prompt_id": p.id,
                "book_unit_number": p.lesson.book_unit_number,
                "lesson_title": p.lesson.title_en or p.lesson.title,
                "image_type": p.prompt_type,
                "file_exists": has_file,
                "file_size_bytes": _file_size(ff) if has_file else None,
                "dimensions": _dimensions(ff) if has_file else None,
                "generation_status": p.generation_status,
                "student_visible": p.is_student_visible,
                "prompt_summary": (p.prompt or "")[:160],
                "is_duplicate": is_dup,
                "recommendation": "approve" if eligible else "hold",
            })

        manifest_path = options["export_manifest"]
        if manifest_path:
            os.makedirs(os.path.dirname(manifest_path) or ".", exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump({"course_slug": slug, "count": len(rows), "items": rows},
                          fh, ensure_ascii=False, indent=2)

        reject_ids = {int(x) for x in (options["reject"] or "").split(",") if x.strip().isdigit()}
        do_write = (options["approve"] or reject_ids) and options["apply"]

        report = {
            "course_slug": slug,
            "status_filter": options["status"],
            "types": types,
            "total_reviewed": len(rows),
            "eligible_for_approval": sum(1 for r in rows if r["recommendation"] == "approve"),
            "skipped_missing_file": sum(1 for r in rows if not r["file_exists"]),
            "skipped_duplicate": sum(1 for r in rows if r["is_duplicate"]),
            "manifest_path": manifest_path,
            "applied": bool(do_write),
            "items": rows,
        }

        if not do_write:
            report["note"] = (
                "DRY-RUN — no media approved. Add --approve --apply to write."
                if (options["approve"] or reject_ids)
                else "REVIEW ONLY — pass --approve --apply to approve eligible images."
            )
            self._emit(report, options["format"])
            return

        approved, rejected = 0, 0
        with transaction.atomic():
            if options["approve"]:
                for p in prompts:
                    r = next(x for x in rows if x["prompt_id"] == p.id)
                    if r["recommendation"] != "approve":
                        continue
                    if p.generation_status == "approved":
                        continue
                    if not _file_on_disk(p.generated_image):   # re-check in txn
                        continue
                    mark_media_approved(p, reviewer=None, note="18.2E batch review")
                    approved += 1
            for pid in reject_ids:
                p = LessonImagePrompt.objects.filter(
                    pk=pid, lesson_id__in=canonical_ids).first()
                if p and p.generation_status in _APPROVABLE_STATUSES:
                    mark_media_rejected(p, reviewer=None, note="18.2E rejected")
                    rejected += 1

        report.update({
            "approved_count": approved,
            "rejected_count": rejected,
            "student_visible_count": approved,
            "affected_book_units": sorted({r["book_unit_number"] for r in rows
                                           if r["recommendation"] == "approve"}),
        })
        self._emit(report, options["format"])

    def _emit(self, report, fmt):
        if fmt == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return
        w = self.stdout.write
        w("=" * 72)
        w("Beginner illustration review " + ("(APPLIED)" if report["applied"] else "(REVIEW/DRY-RUN)"))
        w("=" * 72)
        w(f"Course: {report['course_slug']}  status={report['status_filter']}  types={report['types']}")
        w(f"Total reviewed       : {report['total_reviewed']}")
        w(f"Eligible for approval: {report['eligible_for_approval']}")
        w(f"Skipped missing file : {report['skipped_missing_file']}")
        w(f"Skipped duplicate    : {report['skipped_duplicate']}")
        if report.get("manifest_path"):
            w(f"Manifest written     : {report['manifest_path']}")
        w("-" * 72)
        for r in report["items"]:
            dims = "x".join(map(str, r["dimensions"])) if r["dimensions"] else "?"
            w(f"  BU{r['book_unit_number']:>2} {r['image_type']:<10} "
              f"file={r['file_exists']} {dims} status={r['generation_status']} "
              f"-> {r['recommendation']}  | {r['lesson_title']}")
        if report["applied"]:
            w("-" * 72)
            w(f"Approved={report.get('approved_count')}  rejected={report.get('rejected_count')}  "
              f"student_visible+={report.get('student_visible_count')}  "
              f"book_units={report.get('affected_book_units')}")
        else:
            w(report.get("note", ""))
