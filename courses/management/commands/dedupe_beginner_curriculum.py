"""Safe de-duplication of the Beginner course (Prompt 18.2).

Dev databases accumulated duplicate lessons because TWO seed sources own the
same slug ``onlenco-beginner`` with different layouts:
  * ``seed_onlenco_beginner_48_units`` — canonical: 16 units × 3 = 48 lessons,
    lessons keyed by (course, order 1..48).
  * ``seed_beginner_48_topics`` — legacy: one unit per topic, lessons keyed by
    (course, unit, order), creating a second lesson per order.

This command restores the canonical structure WITHOUT losing student data:

  * DRY-RUN by default. Nothing is written unless ``--apply`` is passed.
  * For each Lesson.order it keeps ONE canonical lesson — the one that best
    matches book_structure.csv and sits in the correct unit.
  * A duplicate carrying ONLY student progress is remapped to the canonical
    lesson (when there is no per-student conflict), then removed.
  * A duplicate carrying non-remappable data (challenge sessions/answers,
    mistakes, teacher assignments) is NEVER deleted — it is skipped with a
    WARNING (which then rolls the whole --apply back, by design).
  * Lessons are regrouped into 16 units of 3; empty/extra units are removed
    (Lesson.unit is SET_NULL, so reassign-then-drop never orphans a lesson).
  * The single CSV/DB title difference is synced from book_structure.csv.
  * After ``--apply`` it re-checks the structure and rolls back if it is not
    the canonical 16×3=48 (transaction.atomic).

No schema changes, no migrations.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.models import (
    ChallengeAnswer, ChallengeSession, Course, CourseLessonProgress,
    CourseUnit, Lesson,
)
from courses.management.commands.verify_beginner_curriculum_structure import (
    _OK_RATIO, _csv_candidates, _ratio,
)

_DEFAULT_SLUG = "onlenco-beginner"
_MAX = CourseUnit.MAX_LESSONS_PER_UNIT  # 3
_CANONICAL_LESSONS = 48
_CANONICAL_UNITS = 16


def _unit_order_for(lesson_order: int) -> int:
    return ((lesson_order - 1) // _MAX) + 1


def _hard_blocked(lesson) -> bool:
    """Data that cannot be safely remapped → the lesson must never be deleted."""
    if ChallengeSession.objects.filter(lesson=lesson).exists():
        return True
    if ChallengeAnswer.objects.filter(question__quiz__lesson=lesson).exists():
        return True
    for rel in ("teacher_assignments", "student_mistakes"):
        mgr = getattr(lesson, rel, None)
        try:
            if mgr is not None and mgr.exists():
                return True
        except Exception:
            pass
    return False


def _progress_users(lesson) -> set:
    return set(
        CourseLessonProgress.objects.filter(lesson=lesson)
        .values_list("user_id", flat=True)
    )


def _relation_score(lesson) -> int:
    """Richness — used only to break ties when picking canonical."""
    score = 1 if getattr(lesson, "quiz", None) is not None else 0
    for rel in ("resources", "media", "checklist_items", "image_prompts",
                "audio_scripts", "tutor_prompts", "student_progress",
                "challenge_sessions"):
        mgr = getattr(lesson, rel, None)
        try:
            score += mgr.count() if mgr is not None else 0
        except Exception:
            pass
    return score


class Command(BaseCommand):
    help = (
        "Safely de-duplicate the Beginner course back to 16 units × 3 = 48 "
        "lessons. DRY-RUN by default; pass --apply to write. Remaps student "
        "progress to the canonical lesson; never deletes non-remappable data."
    )

    def add_arguments(self, parser):
        parser.add_argument("--course-slug", default=_DEFAULT_SLUG)
        parser.add_argument("--csv-path", default=None)
        parser.add_argument("--apply", action="store_true",
                            help="Actually write changes (default: dry-run).")
        parser.add_argument("--format", choices=["text", "json"], default="text")

    # ------------------------------------------------------------------ csv
    def _resolve_csv(self, csv_path):
        if csv_path:
            p = Path(csv_path)
            if not p.exists():
                raise CommandError(f"CSV not found at --csv-path: {p}")
            return p
        for cand in _csv_candidates():
            if cand.exists():
                return cand
        raise CommandError("book_structure.csv not found; pass --csv-path.")

    def _csv_titles(self, path):
        out = {}
        with path.open(newline="", encoding="utf-8") as fh:
            for raw in csv.DictReader(fh):
                try:
                    n = int((raw.get("unit_number") or "").strip())
                except (TypeError, ValueError):
                    continue
                out[n] = (raw.get("title") or "").strip()
        return out

    # ----------------------------------------------------------- canonical
    def _pick_canonical(self, cands, csv_title):
        """Keep the book-aligned lesson: best title match, then correct unit,
        then richest, then oldest, then lowest id. Blocked duplicates are NOT
        forced — their data is remapped to this canonical (see handle)."""
        def keyf(le):
            ratio = _ratio(csv_title, le.title_en or le.title or "") if csv_title else 0.0
            in_unit = 1 if (le.unit_id and le.unit and le.unit.order == _unit_order_for(le.order)) else 0
            created = le.created_at.timestamp() if le.created_at else float("inf")
            return (-round(ratio, 3), -in_unit, -_relation_score(le), created, le.pk)
        return sorted(cands, key=keyf)[0]

    # ---------------------------------------------------------------- handle
    def handle(self, *args, **options):
        apply = options["apply"]
        slug = options["course_slug"]
        csv_path = self._resolve_csv(options["csv_path"])
        csv_titles = self._csv_titles(csv_path)

        course = Course.objects.filter(slug=slug).first()
        if course is None:
            raise CommandError(f"Course not found: slug={slug!r}")

        before = {
            "units": CourseUnit.objects.filter(course=course).count(),
            "lessons": Lesson.objects.filter(course=course).count(),
        }

        lessons = list(Lesson.objects.filter(course=course).order_by("order", "id"))
        by_order: dict[int, list] = {}
        for le in lessons:
            by_order.setdefault(le.order, []).append(le)

        plan_keep, plan_delete, plan_skip, plan_remap, title_syncs = [], [], [], [], []

        for order, cands in sorted(by_order.items()):
            csv_title = csv_titles.get(order, "")
            canonical = self._pick_canonical(cands, csv_title)
            plan_keep.append(canonical)

            cur = canonical.title_en or canonical.title or ""
            if csv_title and _ratio(csv_title, cur) < _OK_RATIO:
                title_syncs.append((canonical, cur, csv_title))

            reserved_users = _progress_users(canonical)  # users already on canonical
            for c in cands:
                if c.pk == canonical.pk:
                    continue
                if _hard_blocked(c):
                    plan_skip.append((c, "non-remappable data (sessions/answers/mistakes/assignments)"))
                    continue
                dup_users = _progress_users(c)
                if dup_users & reserved_users:
                    plan_skip.append((c, "progress conflicts with canonical for the same student"))
                    continue
                if dup_users:
                    plan_remap.append((c, canonical))
                    reserved_users |= dup_users
                plan_delete.append(c)

        report = {
            "course_slug": slug,
            "csv_path": str(csv_path),
            "applied": apply,
            "before": before,
            "planned_deletions": len(plan_delete),
            "planned_remaps": len(plan_remap),
            "planned_skips": len(plan_skip),
            "title_syncs": [
                {"order": le.order, "from": old, "to": new}
                for (le, old, new) in title_syncs
            ],
            "deletion_lesson_ids": sorted(le.pk for le in plan_delete),
            "remaps": [
                {"from_lesson": d.pk, "to_lesson": canon.pk, "order": d.order}
                for (d, canon) in plan_remap
            ],
            "skips": [
                {"lesson_id": le.pk, "order": le.order, "reason": reason}
                for (le, reason) in plan_skip
            ],
        }

        if not apply:
            report["after"] = before
            report["note"] = "DRY-RUN — no changes written. Re-run with --apply."
            self._emit(report, options["format"])
            return

        # ---- APPLY (atomic; rolls back if the result is not canonical) ----
        with transaction.atomic():
            canon_units = {}
            for i in range(1, _CANONICAL_UNITS + 1):
                cu, _ = CourseUnit.objects.update_or_create(
                    course=course, order=i,
                    defaults={"title": f"Group {i}", "title_en": f"Group {i}",
                              "title_ar": f"المجموعة {i}", "is_active": True},
                )
                canon_units[i] = cu
            # Reassign kept lessons to their canonical unit.
            for le in plan_keep:
                target = canon_units.get(_unit_order_for(le.order))
                if target and le.unit_id != target.pk:
                    le.unit = target
                    le.save(update_fields=["unit"])
            # Title syncs.
            for (le, _old, new) in title_syncs:
                le.title = new
                le.title_en = new
                le.save(update_fields=["title", "title_en"])
            # Remap student progress off duplicates BEFORE deleting them.
            remapped = 0
            for (d, canon) in plan_remap:
                remapped += CourseLessonProgress.objects.filter(lesson=d).update(lesson=canon)
            # Delete the now-safe duplicates (cascades regenerable seed content).
            deleted = 0
            for le in plan_delete:
                le.delete()
                deleted += 1
            # Drop empty units (lessons already reassigned).
            removed_units = 0
            for cu in list(CourseUnit.objects.filter(course=course)):
                if not Lesson.objects.filter(unit=cu).exists():
                    cu.delete()
                    removed_units += 1
            # Re-verify canonical structure; rollback if wrong.
            post_lessons = list(Lesson.objects.filter(course=course))
            post_units = list(CourseUnit.objects.filter(course=course))
            order_counts = Counter(le.order for le in post_lessons)
            dups = sum(c - 1 for c in order_counts.values() if c > 1)
            units_with_3 = sum(
                1 for u in post_units
                if Lesson.objects.filter(unit=u).count() == _MAX
            )
            structural_ok = (
                len(post_lessons) == _CANONICAL_LESSONS
                and len(post_units) == _CANONICAL_UNITS
                and units_with_3 == _CANONICAL_UNITS
                and dups == 0
            )
            report.update({
                "deleted_lessons": deleted,
                "remapped_progress": remapped,
                "removed_units": removed_units,
                "after": {"units": len(post_units), "lessons": len(post_lessons),
                          "duplicate_lessons": dups,
                          "units_with_exactly_3_lessons": units_with_3},
                "structural_ok": structural_ok,
            })
            if not structural_ok:
                self._emit(report, options["format"])
                raise CommandError(
                    "Could not reach canonical 16×3=48 safely (see report). "
                    "Rolled back — likely a duplicate carrying non-remappable data."
                )

        self._emit(report, options["format"])

    # --------------------------------------------------------------- output
    def _emit(self, report, fmt):
        if fmt == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return
        w = self.stdout.write
        w("=" * 72)
        w("Beginner curriculum dedupe " + ("(APPLIED)" if report["applied"] else "(DRY-RUN)"))
        w("=" * 72)
        w(f"Course: {report['course_slug']}   CSV: {report['csv_path']}")
        w(f"Before : units={report['before']['units']}  lessons={report['before']['lessons']}")
        a = report.get("after")
        if isinstance(a, dict) and "duplicate_lessons" in a:
            w(f"After  : units={a['units']}  lessons={a['lessons']}  "
              f"dups={a['duplicate_lessons']}  units_with_3={a['units_with_exactly_3_lessons']}")
        elif isinstance(a, dict):
            w(f"After  : units={a['units']}  lessons={a['lessons']}")
        w(f"Planned deletions : {report['planned_deletions']}")
        w(f"Planned remaps    : {report['planned_remaps']} (student progress → canonical)")
        w(f"Planned skips     : {report['planned_skips']} (kept — non-remappable data)")
        for ts in report.get("title_syncs", []):
            w(f"  title sync @order {ts['order']}: {ts['from']!r} -> {ts['to']!r}")
        for s in report.get("skips", []):
            w(f"  SKIP lesson#{s['lesson_id']} (order {s['order']}): {s['reason']}")
        if report["applied"]:
            w(f"Deleted={report.get('deleted_lessons')}  "
              f"remapped_progress={report.get('remapped_progress')}  "
              f"removed_units={report.get('removed_units')}  "
              f"structural_ok={report.get('structural_ok')}")
        else:
            w(report.get("note", ""))
