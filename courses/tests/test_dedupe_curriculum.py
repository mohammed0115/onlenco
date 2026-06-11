"""Prompt 18.2 — safe dedupe + canonical seed lock for the Beginner course."""
from __future__ import annotations

import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from courses.models import (
    Course, CourseLessonProgress, CourseUnit, Lesson,
)

User = get_user_model()


class DedupeBeginnerCurriculumTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")

    # --- helpers -----------------------------------------------------------
    def _pollute(self, orders=range(2, 49)):
        """Mimic the cross-seed duplication: a second lesson per order."""
        for order in orders:
            canon = Lesson.objects.filter(course=self.course, order=order).first()
            Lesson.objects.create(
                course=self.course, order=order, unit=None,
                title=canon.title, title_en=canon.title_en, title_ar=canon.title_ar,
                lesson_type=canon.lesson_type, cefr_level=canon.cefr_level,
                skill=canon.skill, status="draft",
            )

    def _dedupe_json(self, *args):
        out = StringIO()
        call_command("dedupe_beginner_curriculum", "--format", "json", *args, stdout=out)
        return json.loads(out.getvalue())

    # --- tests -------------------------------------------------------------
    def test_dedupe_command_dry_run_does_not_change_counts(self):
        self._pollute()
        before = Lesson.objects.filter(course=self.course).count()
        self._dedupe_json()  # dry-run (no --apply)
        self.assertEqual(Lesson.objects.filter(course=self.course).count(), before)
        self.assertEqual(before, 95)

    def test_dedupe_command_detects_duplicate_lesson_orders(self):
        self._pollute()
        rep = self._dedupe_json()
        self.assertEqual(rep["planned_deletions"], 47)
        self.assertFalse(rep["applied"])

    def test_dedupe_command_apply_restores_48_lessons(self):
        self._pollute()
        rep = self._dedupe_json("--apply")
        self.assertTrue(rep["structural_ok"])
        self.assertEqual(Lesson.objects.filter(course=self.course).count(), 48)

    def test_dedupe_command_apply_restores_16_units_with_3_lessons_each(self):
        self._pollute()
        self._dedupe_json("--apply")
        units = CourseUnit.objects.filter(course=self.course)
        self.assertEqual(units.count(), 16)
        for u in units:
            self.assertEqual(Lesson.objects.filter(unit=u).count(), 3)

    def test_dedupe_command_preserves_canonical_titles_from_csv(self):
        # Corrupt a canonical title, then dedupe should sync it from the CSV.
        le = Lesson.objects.get(course=self.course, order=5)
        original = le.title_en
        le.title_en = "WRONG TITLE ZZZ"
        le.title = "WRONG TITLE ZZZ"
        le.save(update_fields=["title_en", "title"])
        self._dedupe_json("--apply")
        le.refresh_from_db()
        # Restored to a book-matching title (not the corrupted one).
        self.assertNotEqual(le.title_en, "WRONG TITLE ZZZ")
        self.assertNotEqual(le.title_en, "")

    def test_dedupe_command_refuses_to_delete_lesson_with_unmapped_dependencies(self):
        # Two lessons for one order, BOTH carrying student progress → ambiguous.
        student = User.objects.create_user(username="s18@x.com", password="pw")
        canon = Lesson.objects.get(course=self.course, order=7)
        dup = Lesson.objects.create(
            course=self.course, order=7, unit=None,
            title=canon.title, title_en=canon.title_en, title_ar=canon.title_ar,
            lesson_type=canon.lesson_type, cefr_level=canon.cefr_level,
            skill=canon.skill, status="draft",
        )
        CourseLessonProgress.objects.create(user=student, lesson=canon, video_completed=True)
        CourseLessonProgress.objects.create(user=student, lesson=dup, video_completed=True)
        before = Lesson.objects.filter(course=self.course).count()
        # --apply must roll back (can't reach canonical safely) and delete nothing.
        with self.assertRaises(CommandError):
            call_command("dedupe_beginner_curriculum", "--apply", stdout=StringIO())
        self.assertEqual(Lesson.objects.filter(course=self.course).count(), before)
        self.assertTrue(Lesson.objects.filter(pk=dup.pk).exists())

    def test_dedupe_command_is_idempotent_after_apply(self):
        self._pollute()
        self._dedupe_json("--apply")
        rep2 = self._dedupe_json("--apply")
        self.assertTrue(rep2["structural_ok"])
        self.assertEqual(rep2["planned_deletions"], 0)
        self.assertEqual(Lesson.objects.filter(course=self.course).count(), 48)

    def test_seed_onlenco_beginner_is_idempotent(self):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        self.assertEqual(Lesson.objects.filter(course=self.course).count(), 48)
        self.assertEqual(CourseUnit.objects.filter(course=self.course).count(), 16)

    def test_legacy_seed_commands_do_not_duplicate_onlenco_beginner(self):
        # The canonical 16×3 course exists (setUpTestData) → topics seed skips.
        before = Lesson.objects.filter(course=self.course).count()
        out = StringIO()
        call_command("seed_beginner_48_topics", "--confirm", stdout=out)
        self.assertEqual(Lesson.objects.filter(course=self.course).count(), before)
        self.assertIn("Skipping", out.getvalue())

    def test_verify_command_passes_after_dedupe(self):
        self._pollute()
        self._dedupe_json("--apply")
        # verify --fail-on-mismatch must NOT raise on the cleaned course.
        call_command(
            "verify_beginner_curriculum_structure", "--fail-on-mismatch",
            stdout=StringIO(),
        )
