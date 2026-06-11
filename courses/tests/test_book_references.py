"""Prompt 18.3 — additive book references (book_unit_number / book_page) on Lesson."""
from __future__ import annotations

import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from courses.models import Course, CourseLevel, Lesson


class LessonBookFieldModelTests(TestCase):
    def test_lesson_book_fields_are_optional(self):
        level, _ = CourseLevel.objects.get_or_create(code="A0", defaults={"name": "A0", "order": 1})
        course = Course.objects.create(title="T", slug="t-book", level=level, status="draft")
        # Create WITHOUT the new fields → they default to None/blank (additive).
        bare = Lesson.objects.create(course=course, title="L1", order=1)
        self.assertIsNone(bare.book_unit_number)
        self.assertIsNone(bare.book_page)
        self.assertEqual(bare.book_reference, "")
        # Create WITH the new fields.
        full = Lesson.objects.create(
            course=course, title="L2", order=2,
            book_unit_number=2, book_page=18, book_reference="EFE L1",
        )
        full.refresh_from_db()
        self.assertEqual(full.book_unit_number, 2)
        self.assertEqual(full.book_page, 18)
        self.assertEqual(full.book_reference, "EFE L1")


class SeedBookReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")

    def _lessons(self):
        return list(Lesson.objects.filter(course=self.course).order_by("order"))

    def _verify_json(self, *args):
        out = StringIO()
        call_command("verify_beginner_curriculum_structure", "--format", "json", *args, stdout=out)
        return json.loads(out.getvalue())["summary"]

    def test_seed_fills_book_unit_number_for_all_48(self):
        lessons = self._lessons()
        self.assertEqual(len(lessons), 48)
        self.assertTrue(all(le.book_unit_number is not None for le in lessons))
        self.assertTrue(all(le.book_unit_number == le.order for le in lessons))

    def test_book_unit_numbers_are_1_to_48_without_duplicates(self):
        nums = sorted(le.book_unit_number for le in self._lessons())
        self.assertEqual(nums, list(range(1, 49)))

    def test_seed_fills_book_page_and_reference(self):
        lessons = self._lessons()
        # book_structure.csv ships a page for every unit → all 48 filled.
        self.assertTrue(all(le.book_page is not None for le in lessons))
        self.assertTrue(all(le.book_reference for le in lessons))

    def test_reseed_does_not_duplicate_or_change_count(self):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        self.assertEqual(Lesson.objects.filter(course=self.course).count(), 48)

    def test_verify_reports_book_reference_metrics_ok(self):
        s = self._verify_json("--fail-on-mismatch")
        self.assertEqual(s["lessons_with_book_unit_number"], 48)
        self.assertEqual(s["lessons_missing_book_unit_number"], 0)
        self.assertEqual(s["duplicate_book_unit_numbers"], [])
        self.assertTrue(s["book_refs_ok"])
        self.assertFalse(s["has_mismatch"])

    def test_verify_detects_missing_book_unit_number(self):
        le = self._lessons()[0]
        le.book_unit_number = None
        le.save(update_fields=["book_unit_number"])
        s = self._verify_json()
        self.assertGreaterEqual(s["lessons_missing_book_unit_number"], 1)
        self.assertFalse(s["book_refs_ok"])
        self.assertTrue(s["has_mismatch"])

    def test_verify_detects_duplicate_book_unit_number(self):
        le = Lesson.objects.get(course=self.course, order=5)
        le.book_unit_number = 4  # now 4 appears twice
        le.save(update_fields=["book_unit_number"])
        s = self._verify_json()
        self.assertIn(4, s["duplicate_book_unit_numbers"])
        self.assertTrue(s["has_mismatch"])

    def test_verify_detects_missing_book_page_present_in_csv(self):
        le = self._lessons()[0]
        le.book_page = None
        le.save(update_fields=["book_page"])
        s = self._verify_json()
        self.assertGreaterEqual(s["missing_book_page_present_in_csv"], 1)

    def test_dedupe_preserves_book_fields(self):
        # Pollute with book-field-less duplicates, dedupe, confirm 48 keep refs.
        for order in range(2, 49):
            canon = Lesson.objects.get(course=self.course, order=order)
            Lesson.objects.create(
                course=self.course, order=order, unit=None,
                title=canon.title, title_en=canon.title_en, title_ar=canon.title_ar,
                lesson_type=canon.lesson_type, cefr_level=canon.cefr_level,
                skill=canon.skill, status="draft",
            )
        call_command("dedupe_beginner_curriculum", "--apply", stdout=StringIO())
        lessons = Lesson.objects.filter(course=self.course)
        self.assertEqual(lessons.count(), 48)
        self.assertEqual(lessons.filter(book_unit_number__isnull=False).count(), 48)
