"""Generate ONLY the missing Beginner illustration images (Prompt 18.2D).

Scope: vocabulary / grammar / quiz illustrations for the canonical 48 lessons of
``onlenco-beginner`` whose ``LessonImagePrompt`` has no usable file. It NEVER
touches cover images, audio, approved media, non-canonical lessons, progress, or
quizzes, and never regenerates an image that already has a valid file.

DRY-RUN by default. A ``--max-cost-usd`` budget guard blocks the batch when the
estimated cost would exceed the cap. Generated images land at ``needs_review``
(NOT student-visible) — approval is a separate phase (18.2E).

Reuses the existing ``media_generation_service.generate_lesson_image`` (which
goes through the ai_usage wrapper); no new provider is introduced.
"""
from __future__ import annotations

import json
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from courses.models import Course, Lesson, LessonImagePrompt
from courses.services import media_generation_service as mgs

_DEFAULT_SLUG = "onlenco-beginner"
_EXPECTED = 48
_COVER_TYPE = "cover"
_ALLOWED_TYPES = ("vocabulary", "grammar", "quiz")


def _file_on_disk(filefield) -> bool:
    if not filefield:
        return False
    try:
        return filefield.storage.exists(filefield.name)
    except Exception:
        return False


def _is_missing(prompt) -> bool:
    """Missing == no usable file (empty field or file gone from storage)."""
    return not (prompt.generated_image and _file_on_disk(prompt.generated_image))


class Command(BaseCommand):
    help = (
        "Generate ONLY missing Beginner illustration images (vocabulary/grammar/"
        "quiz) in a limited, budget-guarded batch. DRY-RUN by default. Never "
        "touches covers, audio, approved media, or non-canonical lessons."
    )

    def add_arguments(self, parser):
        parser.add_argument("--course-slug", default=_DEFAULT_SLUG)
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--apply", action="store_true",
                            help="Actually generate (overrides default dry-run).")
        parser.add_argument("--limit", type=int, default=12)
        parser.add_argument("--types", default=",".join(_ALLOWED_TYPES))
        parser.add_argument("--book-unit", type=int, default=None)
        parser.add_argument("--from-book-unit", type=int, default=None)
        parser.add_argument("--to-book-unit", type=int, default=None)
        parser.add_argument("--max-cost-usd", type=float, default=0.50)
        parser.add_argument("--provider", default="",
                            help="Accepted for parity; the project's existing image "
                                 "provider is always used.")
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
        if len(canonical) != _EXPECTED:
            raise CommandError(
                f"Refusing to generate: expected {_EXPECTED} canonical lessons, "
                f"found {len(canonical)}."
            )
        canonical_by_id = {le.pk: le for le in canonical}

        # cover is NEVER generated here.
        types = [t.strip() for t in (options["types"] or "").split(",") if t.strip()]
        types = [t for t in types if t in _ALLOWED_TYPES]
        if not types:
            raise CommandError(f"--types must be a subset of {_ALLOWED_TYPES}.")

        # Candidate prompts (canonical lessons, requested illustration types only).
        prompts = (
            LessonImagePrompt.objects
            .filter(lesson_id__in=canonical_by_id, prompt_type__in=types)
            .select_related("lesson")
            .order_by("lesson__book_unit_number", "prompt_type", "id")
        )

        bu, frm, to = options["book_unit"], options["from_book_unit"], options["to_book_unit"]

        def in_range(n):
            if bu is not None and n != bu:
                return False
            if frm is not None and n < frm:
                return False
            if to is not None and n > to:
                return False
            return True

        missing = [
            p for p in prompts
            if _is_missing(p) and in_range(p.lesson.book_unit_number)
        ]
        skipped_existing = sum(1 for p in prompts if not _is_missing(p))

        batch = missing[: max(0, options["limit"])]
        per_image = mgs._est("ONLENCO_MEDIA_IMAGE_COST_USD", "0.02")
        est_cost = (per_image * len(batch)).quantize(Decimal("0.0001"))
        max_cost = Decimal(str(options["max_cost_usd"]))
        budget_exceeded = est_cost > max_cost

        report = {
            "course_slug": slug,
            "applied": apply,
            "canonical_lessons": len(canonical),
            "types": types,
            "total_missing_illustrations": len(missing),
            "planned_generation_count": len(batch),
            "book_units_in_batch": sorted({p.lesson.book_unit_number for p in batch}),
            "estimated_cost_usd": str(est_cost),
            "max_cost_usd": str(max_cost),
            "budget_exceeded": budget_exceeded,
            "skipped_existing_media": skipped_existing,
            "regeneration_performed_for_existing_media": False,
        }

        if not apply or budget_exceeded:
            if budget_exceeded:
                report["blocked_reason"] = "budget_exceeded"
            report["generated_count"] = 0
            report["note"] = (
                "BUDGET EXCEEDED — nothing generated." if budget_exceeded
                else "DRY-RUN — no images generated. Re-run with --apply."
            )
            self._emit(report, options["format"])
            return

        # ---- APPLY (real generation, one image at a time) -----------------
        generated, failed, skipped = 0, 0, 0
        failures, affected = [], set()
        for p in batch:
            if not _is_missing(p):          # idempotency re-check
                skipped += 1
                continue
            outcome, detail = mgs.generate_lesson_image(p, actor=None)
            if outcome == "generated":
                generated += 1
                affected.add(p.lesson.book_unit_number)
            elif outcome == "skipped":
                skipped += 1
            else:
                failed += 1
                failures.append({"prompt_id": p.id, "book_unit": p.lesson.book_unit_number,
                                 "type": p.prompt_type, "detail": detail})
        report.update({
            "generated_count": generated,
            "failed_count": failed,
            "skipped_count": skipped,
            "affected_book_units": sorted(affected),
            "failures": failures,
        })
        self._emit(report, options["format"])

    def _emit(self, report, fmt):
        if fmt == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return
        w = self.stdout.write
        w("=" * 72)
        w("Generate missing Beginner illustrations "
          + ("(APPLIED)" if report["applied"] and not report.get("budget_exceeded") else "(DRY-RUN)"))
        w("=" * 72)
        w(f"Course: {report['course_slug']}  canonical_lessons={report['canonical_lessons']}")
        w(f"Types               : {report['types']}")
        w(f"Total missing        : {report['total_missing_illustrations']}")
        w(f"Planned this batch   : {report['planned_generation_count']}  "
          f"book_units={report['book_units_in_batch']}")
        w(f"Estimated cost (USD) : {report['estimated_cost_usd']}  (cap {report['max_cost_usd']})")
        w(f"Skipped existing     : {report['skipped_existing_media']}")
        if report.get("budget_exceeded"):
            w("BUDGET EXCEEDED — nothing generated.")
        elif report["applied"]:
            w(f"Generated={report.get('generated_count')}  failed={report.get('failed_count')}  "
              f"skipped={report.get('skipped_count')}  "
              f"affected_book_units={report.get('affected_book_units')}")
            w("regeneration_performed_for_existing_media=False  (status=needs_review, not student-visible)")
        else:
            w(report.get("note", ""))
