"""Read-only verification of the seeded Beginner course against book_structure.csv
(Prompt 18.1).

This command NEVER writes to the database. It loads the canonical book
structure (the 48 EFE units extracted to ``book_structure.csv``) and compares
it, in order, against the seeded ``onlenco-beginner`` course:

    book unit_number (1..48)  ->  Lesson.order
    every 3 lessons           ->  one CourseUnit (16 units total)

Title differences are expected (the platform ships ORIGINAL copy, the CSV holds
the book's wording), so titles are matched with a tolerant similarity ratio
(``difflib``) rather than an exact compare. The command prints a summary, a
per-row mapping table, and recommendations. With ``--fail-on-mismatch`` it
exits non-zero so CI can gate on structural drift.

Stdlib only — no external dependencies, no migrations, no seed.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from courses.models import Course, CourseUnit, Lesson

# Title similarity thresholds.
_OK_RATIO = 0.85       # >= → titles considered matching
_WARN_RATIO = 0.60     # >= → close but flagged; below → clear mismatch

_DEFAULT_SLUG = "onlenco-beginner"


def _csv_candidates():
    base = Path(settings.BASE_DIR)
    return [
        base / "book_structure.csv",
        base / "courses" / "data" / "book_structure.csv",
        base / "docs" / "book_structure.csv",
    ]


def _normalize_title(s: str) -> str:
    """Lower-case, drop the leading 'Vocabulary' marker, strip punctuation and
    collapse whitespace, so 'Vocabulary Countries' ≈ 'Countries'."""
    s = (s or "").strip().lower()
    s = re.sub(r"^\s*vocabulary\b", " ", s)
    s = s.replace("vocabulary", " ")
    s = re.sub(r"[^a-z0-9؀-ۿ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


class Command(BaseCommand):
    help = (
        "READ-ONLY: verify the seeded Beginner course matches book_structure.csv "
        "(48 lessons in 16 units of 3). Never writes to the DB."
    )

    def add_arguments(self, parser):
        parser.add_argument("--csv-path", default=None,
                            help="Path to book_structure.csv (auto-detected if omitted).")
        parser.add_argument("--course-slug", default=_DEFAULT_SLUG,
                            help=f"Course slug to verify (default {_DEFAULT_SLUG}).")
        parser.add_argument("--fail-on-mismatch", action="store_true",
                            help="Exit non-zero when any mismatch is found (for CI).")
        parser.add_argument("--format", choices=["text", "json"], default="text",
                            help="Output format (default text).")

    # ------------------------------------------------------------------ load
    def _resolve_csv(self, csv_path):
        if csv_path:
            p = Path(csv_path)
            if not p.exists():
                raise CommandError(f"CSV not found at --csv-path: {p}")
            return p
        for cand in _csv_candidates():
            if cand.exists():
                return cand
        raise CommandError(
            "book_structure.csv not found. Pass --csv-path, or place it at "
            "<BASE_DIR>/book_structure.csv (or courses/data/book_structure.csv)."
        )

    def _read_csv(self, path: Path) -> list[dict]:
        rows = []
        with path.open(newline="", encoding="utf-8") as fh:
            for raw in csv.DictReader(fh):
                try:
                    n = int((raw.get("unit_number") or "").strip())
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "unit_number": n,
                    "type": (raw.get("type") or "").strip(),
                    "title": (raw.get("title") or "").strip(),
                    "book_page": (raw.get("book_page") or "").strip(),
                    "new_skill": (raw.get("new_skill") or "").strip(),
                })
        rows.sort(key=lambda r: r["unit_number"])
        return rows

    # ----------------------------------------------------------------- handle
    def handle(self, *args, **options):
        csv_path = self._resolve_csv(options["csv_path"])
        rows = self._read_csv(csv_path)

        slug = options["course_slug"]
        course = Course.objects.filter(slug=slug).first()
        units = list(CourseUnit.objects.filter(course=course).order_by("order")) if course else []
        lessons = list(Lesson.objects.filter(course=course).order_by("order", "id")) if course else []
        lessons_by_order = {}
        for le in lessons:
            lessons_by_order.setdefault(le.order, le)  # first wins on dup order

        # --- per-row mapping ------------------------------------------------
        mapping = []
        csv_orders = {r["unit_number"] for r in rows}
        matched_titles = mismatched_titles = type_mismatches = missing = 0

        for r in rows:
            le = lessons_by_order.get(r["unit_number"])
            cu_order = (
                ((r["unit_number"] - 1) // CourseUnit.MAX_LESSONS_PER_UNIT) + 1
                if r["unit_number"] else None
            )
            if le is None:
                missing += 1
                mapping.append({**self._csv_cols(r), "platform_course_unit_order": cu_order,
                                "platform_lesson_order": None, "platform_lesson_title": None,
                                "platform_skill": None, "platform_lesson_type": None,
                                "title_ratio": 0.0, "status": "MISSING"})
                continue

            ratio = _ratio(r["title"], le.title_en or le.title or "")
            is_vocab = (r["type"].lower() == "vocab")
            type_ok = (le.lesson_type == "vocabulary") if is_vocab else (le.lesson_type != "vocabulary")
            if ratio >= _OK_RATIO:
                matched_titles += 1
            else:
                mismatched_titles += 1
            if not type_ok:
                type_mismatches += 1
            status = "OK" if (ratio >= _OK_RATIO and type_ok) else "WARNING"
            mapping.append({
                **self._csv_cols(r),
                "platform_course_unit_order": le.unit.order if le.unit else cu_order,
                "platform_lesson_order": le.order,
                "platform_lesson_title": le.title_en or le.title,
                "platform_skill": le.skill,
                "platform_lesson_type": le.lesson_type,
                "title_ratio": round(ratio, 3),
                "status": status,
            })

        # --- extra lessons (present in course, absent from CSV) -------------
        extra = 0
        for le in lessons:
            if le.order not in csv_orders:
                extra += 1
                mapping.append({
                    "csv_unit_number": None, "csv_title": None, "csv_type": None,
                    "csv_skill": None, "csv_page": None,
                    "platform_course_unit_order": le.unit.order if le.unit else None,
                    "platform_lesson_order": le.order,
                    "platform_lesson_title": le.title_en or le.title,
                    "platform_skill": le.skill, "platform_lesson_type": le.lesson_type,
                    "title_ratio": 0.0, "status": "EXTRA",
                })

        units_with_3 = sum(
            1 for u in units
            if Lesson.objects.filter(unit=u).count() == CourseUnit.MAX_LESSONS_PER_UNIT
        )

        # Duplicate lesson orders expose seed pollution (the same book unit
        # seeded more than once into the course). These hide from missing/extra
        # because their order is still within 1..48, so surface them explicitly.
        order_counts = Counter(le.order for le in lessons)
        duplicate_orders = sorted(o for o, c in order_counts.items() if c > 1)
        duplicate_lessons = sum(c - 1 for c in order_counts.values() if c > 1)

        summary = {
            "csv_path": str(csv_path),
            "course_slug": slug,
            "course_found": course is not None,
            "csv_rows": len(rows),
            "course_units": len(units),
            "lessons": len(lessons),
            "units_with_exactly_3_lessons": units_with_3,
            "matched_titles": matched_titles,
            "mismatched_titles": mismatched_titles,
            "type_mismatches": type_mismatches,
            "missing_lessons": missing,
            "extra_lessons": extra,
            "duplicate_order_count": len(duplicate_orders),
            "duplicate_lessons": duplicate_lessons,
        }

        structural_ok = (
            course is not None
            and len(rows) == 48
            and len(lessons) == 48
            and len(units) == 16
            and units_with_3 == len(units)
            and duplicate_lessons == 0
        )

        # --- Book references (Prompt 18.3) ----------------------------------
        csv_by_order_page = {}
        for r in rows:
            try:
                csv_by_order_page[r["unit_number"]] = (
                    int(r["book_page"]) if r["book_page"] else None
                )
            except (TypeError, ValueError):
                csv_by_order_page[r["unit_number"]] = None
        book_units = [le.book_unit_number for le in lessons]
        bun_counter = Counter(b for b in book_units if b is not None)
        lessons_with_bun = sum(1 for b in book_units if b is not None)
        lessons_with_page = sum(1 for le in lessons if le.book_page is not None)
        dup_bun = sorted(b for b, c in bun_counter.items() if c > 1)
        bun_out_of_range = sorted({b for b in book_units if b is not None and not (1 <= b <= 48)})
        # book_unit_number should equal the platform order (== CSV unit_number).
        bun_position_mismatch = sum(
            1 for le in lessons
            if le.book_unit_number is not None and le.book_unit_number != le.order
        )
        # book_page expected wherever the CSV provides one for that order.
        missing_page_with_csv = sum(
            1 for le in lessons
            if le.order in csv_orders
            and (csv_by_order_page.get(le.order) is not None)
            and le.book_page is None
        )
        summary.update({
            "lessons_with_book_unit_number": lessons_with_bun,
            "lessons_missing_book_unit_number": len(lessons) - lessons_with_bun,
            "lessons_with_book_page": lessons_with_page,
            "lessons_missing_book_page": len(lessons) - lessons_with_page,
            "duplicate_book_unit_numbers": dup_bun,
            "book_unit_numbers_out_of_range": bun_out_of_range,
            "book_unit_position_mismatch": bun_position_mismatch,
            "missing_book_page_present_in_csv": missing_page_with_csv,
        })
        book_refs_ok = (
            course is not None
            and (len(lessons) - lessons_with_bun) == 0
            and not dup_bun
            and not bun_out_of_range
            and bun_position_mismatch == 0
        )
        summary["book_refs_ok"] = book_refs_ok

        has_mismatch = (
            not structural_ok
            or not book_refs_ok
            or mismatched_titles > 0
            or type_mismatches > 0
            or missing > 0
            or extra > 0
        )
        summary["structural_ok"] = structural_ok
        summary["has_mismatch"] = has_mismatch

        if options["format"] == "json":
            self.stdout.write(json.dumps(
                {"summary": summary, "mapping": mapping}, ensure_ascii=False, indent=2))
        else:
            self._print_text(summary, mapping)

        if options["fail_on_mismatch"] and has_mismatch:
            raise CommandError("Curriculum structure mismatch detected (--fail-on-mismatch).")

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _csv_cols(r):
        return {
            "csv_unit_number": r["unit_number"], "csv_title": r["title"],
            "csv_type": r["type"], "csv_skill": r["new_skill"], "csv_page": r["book_page"],
        }

    def _print_text(self, summary, mapping):
        w = self.stdout.write
        w("=" * 72)
        w("Beginner curriculum structure verification (READ-ONLY)")
        w("=" * 72)
        w(f"CSV: {summary['csv_path']}")
        w(f"Course slug: {summary['course_slug']}  (found={summary['course_found']})")
        w("")
        w("Summary")
        w("-" * 72)
        for label, key in [
            ("CSV rows", "csv_rows"), ("Course units", "course_units"),
            ("Lessons", "lessons"), ("Units with exactly 3 lessons", "units_with_exactly_3_lessons"),
            ("Matched titles", "matched_titles"), ("Mismatched titles", "mismatched_titles"),
            ("Type mismatches", "type_mismatches"), ("Missing lessons", "missing_lessons"),
            ("Extra lessons", "extra_lessons"),
            ("Duplicate-order lessons", "duplicate_lessons"),
            ("Lessons with book_unit_number", "lessons_with_book_unit_number"),
            ("Lessons missing book_unit_number", "lessons_missing_book_unit_number"),
            ("Lessons with book_page", "lessons_with_book_page"),
            ("Lessons missing book_page", "lessons_missing_book_page"),
            ("book_unit position mismatch", "book_unit_position_mismatch"),
        ]:
            w(f"  {label:<34}: {summary[key]}")
        w(f"  {'Duplicate book_unit_numbers':<34}: {summary['duplicate_book_unit_numbers']}")
        w(f"  {'book_unit out of range':<34}: {summary['book_unit_numbers_out_of_range']}")
        w(f"  {'Structural OK':<34}: {summary['structural_ok']}")
        w(f"  {'Book refs OK':<34}: {summary['book_refs_ok']}")
        w("")
        w("Mapping (csv# | type | csv title -> platform lesson | skill/type | page | status)")
        w("-" * 72)
        for m in mapping:
            w("  {cn:>3} | {ct:<6} | {ctitle:<28.28} -> {ptitle:<26.26} | "
              "{pskill:<10.10}/{ptype:<10.10} | p{page:<4} | {st}".format(
                  cn=("--" if m["csv_unit_number"] is None else m["csv_unit_number"]),
                  ct=(m["csv_type"] or "-"),
                  ctitle=(m["csv_title"] or "(none)"),
                  ptitle=(m["platform_lesson_title"] or "(missing)"),
                  pskill=(m["platform_skill"] or "-"),
                  ptype=(m["platform_lesson_type"] or "-"),
                  page=(m["csv_page"] or "-"),
                  st=m["status"],
              ))
        w("")
        w("Recommendations")
        w("-" * 72)
        if summary["structural_ok"] and not summary["has_mismatch"]:
            w("  ✓ Structure matches the CSV. No changes needed.")
        else:
            if summary["mismatched_titles"]:
                w(f"  • {summary['mismatched_titles']} title(s) differ — a title-only "
                  "sync of the seed data file may be worth considering (not required).")
            if summary["type_mismatches"]:
                w(f"  • {summary['type_mismatches']} lesson_type/vocab mismatch(es) to review.")
            if summary["missing_lessons"] or summary["extra_lessons"]:
                w(f"  • {summary['missing_lessons']} missing / {summary['extra_lessons']} extra "
                  "lessons vs the CSV — investigate before any sync.")
            if summary["duplicate_lessons"]:
                w(f"  • {summary['duplicate_lessons']} duplicate-order lesson(s) → the course "
                  "was seeded by more than one source. Reconcile to a single clean seed "
                  "(16 units × 3) before any sync.")
            if not summary["course_found"]:
                w("  • Course not found — run the existing seed (seed_onlenco_beginner_48_units).")
        w("  • book_page is reported from the CSV only; there is no Lesson.book_page "
          "field yet. Adding book_page / book_unit_number would be an additive, "
          "optional migration (not done here).")
        w("  • Multiple A0 seed sources exist (Python seed, beginner_topics JSON, "
          "daily_learning templates, import_a0_curriculum). Keep onlenco-beginner as "
          "the single source of truth for THIS course to avoid drift.")
