"""Prompt 18.1 — read-only verification command for the Beginner curriculum."""
from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from courses.models import Course, CourseUnit, Lesson


def _write_csv(path, rows):
    """rows: list of (unit_number, type, title, page)."""
    lines = ["unit_number,type,title,book_page,new_language,vocabulary,new_skill"]
    for n, typ, title, page in rows:
        lines.append(f'{n},{typ},"{title}",{page},,,')
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class VerifyCurriculumStructureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Build the canonical clean course (16 units × 3 = 48 lessons).
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")
        cls.lessons = list(Lesson.objects.filter(course=cls.course).order_by("order"))

    def _matching_csv(self, path):
        """A CSV whose titles exactly match the seeded lessons → guaranteed OK."""
        rows = []
        for le in self.lessons:
            typ = "vocab" if le.lesson_type == "vocabulary" else "lesson"
            rows.append((le.order, typ, le.title_en or le.title, le.order))
        _write_csv(path, rows)

    def _run(self, *args):
        out = StringIO()
        call_command("verify_beginner_curriculum_structure", *args, stdout=out)
        return out.getvalue()

    def _run_json(self, *args):
        return json.loads(self._run("--format", "json", *args))

    # 1 — read-only: no Course/Unit/Lesson row counts change
    def test_command_is_read_only(self):
        before = (Course.objects.count(), CourseUnit.objects.count(), Lesson.objects.count())
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "book_structure.csv"
            self._matching_csv(csv_path)
            self._run_json("--csv-path", str(csv_path))
        after = (Course.objects.count(), CourseUnit.objects.count(), Lesson.objects.count())
        self.assertEqual(before, after)

    # 2 — onlenco-beginner has 48 lessons
    def test_reports_48_lessons(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "book_structure.csv"
            self._matching_csv(csv_path)
            data = self._run_json("--csv-path", str(csv_path))
        self.assertEqual(data["summary"]["lessons"], 48)

    # 3 — every CourseUnit has exactly 3 lessons (16 units)
    def test_reports_16_units_of_three(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "book_structure.csv"
            self._matching_csv(csv_path)
            data = self._run_json("--csv-path", str(csv_path))
        self.assertEqual(data["summary"]["course_units"], 16)
        self.assertEqual(data["summary"]["units_with_exactly_3_lessons"], 16)
        self.assertEqual(data["summary"]["duplicate_lessons"], 0)

    # 4 — reads CSV from --csv-path
    def test_reads_csv_from_path(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "book_structure.csv"
            self._matching_csv(csv_path)
            data = self._run_json("--csv-path", str(csv_path))
        self.assertEqual(data["summary"]["csv_rows"], 48)
        self.assertEqual(data["summary"]["csv_path"], str(csv_path))

    # 5 — detects a title mismatch without touching data
    def test_detects_title_mismatch(self):
        before = Lesson.objects.count()
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "book_structure.csv"
            self._matching_csv(csv_path)
            # Corrupt one title so it can't match.
            text = csv_path.read_text(encoding="utf-8").splitlines()
            text[1] = text[1].replace(
                self.lessons[0].title_en or self.lessons[0].title,
                "Completely Different Topic Zzz",
            )
            csv_path.write_text("\n".join(text) + "\n", encoding="utf-8")
            data = self._run_json("--csv-path", str(csv_path))
        self.assertGreaterEqual(data["summary"]["mismatched_titles"], 1)
        self.assertTrue(data["summary"]["has_mismatch"])
        self.assertEqual(Lesson.objects.count(), before)  # unchanged

    # 6 — --fail-on-mismatch raises on mismatch
    def test_fail_on_mismatch_raises(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "book_structure.csv"
            # Only 2 rows → structural mismatch (csv_rows != 48).
            _write_csv(csv_path, [(1, "lesson", "X", 1), (2, "vocab", "Y", 2)])
            with self.assertRaises(CommandError):
                self._run("--csv-path", str(csv_path), "--fail-on-mismatch")

    # 7 — OK when the structure matches (no raise even with --fail-on-mismatch)
    def test_ok_when_matching(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "book_structure.csv"
            self._matching_csv(csv_path)
            data = self._run_json("--csv-path", str(csv_path))
            self.assertTrue(data["summary"]["structural_ok"])
            self.assertFalse(data["summary"]["has_mismatch"])
            # Must not raise with the gate on.
            self._run("--csv-path", str(csv_path), "--fail-on-mismatch")

    # 8 — does not depend on book_structure.md
    def test_does_not_read_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "book_structure.csv"
            self._matching_csv(csv_path)
            # No .md file exists in the temp dir; command must still work.
            data = self._run_json("--csv-path", str(csv_path))
        self.assertTrue(data["summary"]["course_found"])

    # 9 — missing CSV is a clear error, not a crash
    def test_missing_csv_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._run("--csv-path", "/nonexistent/book_structure.csv")
