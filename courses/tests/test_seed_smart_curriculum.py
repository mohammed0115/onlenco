"""Contract tests for the ``seed_smart_curriculum`` management command.

Pins the rules that make the curriculum a real product (vs random
fixture noise):
  - 7 CEFR levels, each with a published course.
  - Exactly 3 units per course, exactly 3 lessons per unit (the model
    cap is 3 — we want every unit complete and publishable).
  - Every lesson has a quiz with ≥3 questions.
  - 7 books, each with 3 chapters and 3 comprehension Qs.
  - A0 + A1 are free; the others are paid.
  - Lesson content carries Arabic + English + an AI Tutor Drill.
  - Re-running the command does not duplicate rows.
"""
from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson, LessonQuiz, LessonQuestion,
)
from library.models import Book, Chapter, ComprehensionQuestion


User = get_user_model()


def _seed():
    """Convenience — runs the command quietly."""
    out = StringIO()
    call_command("seed_smart_curriculum", stdout=out)
    return out.getvalue()


class SmartCurriculumSeedTests(TestCase):
    """One-shot seed; assert the resulting database matches the contract."""

    @classmethod
    def setUpTestData(cls):
        # Author resolution needs a superuser; create one once for the class.
        cls.admin = User.objects.create_superuser(
            username="seedadmin@x.com",
            email="seedadmin@x.com",
            password="seedpwadminx",
        )
        _seed()

    # ---- 1 ----
    def test_seed_smart_curriculum_command_runs_without_error(self):
        # Re-running inside the test gives us a fresh idempotency check.
        out = _seed()
        self.assertIn("Seeded", out)

    # ---- 2 ----
    def test_seed_creates_all_cefr_levels(self):
        for code in ("A0", "A1", "A2", "B1", "B2", "C1", "C2"):
            self.assertTrue(
                CourseLevel.objects.filter(code=code).exists(),
                f"CEFR level {code} missing",
            )

    # ---- 3 ----
    def test_each_cefr_level_has_course(self):
        for code in ("A0", "A1", "A2", "B1", "B2", "C1", "C2"):
            self.assertTrue(
                Course.objects.filter(level__code=code, status="published").exists(),
                f"Published course for {code} missing",
            )

    # ---- 4 ----
    def test_each_course_has_three_units(self):
        for course in Course.objects.all():
            self.assertEqual(
                course.units.count(), 3,
                f"Course {course.slug} has {course.units.count()} units (want 3)",
            )

    # ---- 5 ----
    def test_each_unit_has_exactly_three_lessons(self):
        for unit in CourseUnit.objects.all():
            self.assertEqual(
                unit.lessons.count(), 3,
                f"Unit {unit.pk} has {unit.lessons.count()} lessons (want 3)",
            )

    # ---- 6 ----
    def test_each_lesson_has_quiz(self):
        for lesson in Lesson.objects.all():
            self.assertTrue(
                LessonQuiz.objects.filter(lesson=lesson).exists(),
                f"Lesson {lesson.pk} missing a quiz",
            )

    # ---- 7 ----
    def test_each_quiz_has_at_least_three_questions(self):
        for quiz in LessonQuiz.objects.all():
            self.assertGreaterEqual(
                quiz.questions.count(), 3,
                f"Quiz {quiz.pk} has {quiz.questions.count()} Qs (want ≥3)",
            )

    # ---- 8 ----
    def test_library_books_created_for_all_levels(self):
        for code in ("A0", "A1", "A2", "B1", "B2", "C1", "C2"):
            self.assertTrue(
                Book.objects.filter(level=code, is_published=True).exists(),
                f"Book for level {code} missing",
            )

    # ---- 9 ----
    def test_each_book_has_three_chapters(self):
        for book in Book.objects.all():
            self.assertEqual(
                book.chapters.count(), 3,
                f"Book '{book.title}' has {book.chapters.count()} chapters (want 3)",
            )

    # ---- 10 ----
    def test_each_chapter_has_three_comprehension_questions(self):
        for chapter in Chapter.objects.all():
            self.assertEqual(
                chapter.comprehension_questions.count(), 3,
                f"Chapter {chapter.pk} has {chapter.comprehension_questions.count()} comp Qs (want 3)",
            )

    # ---- 11 ----
    def test_seed_is_idempotent_no_duplicates(self):
        before_counts = (
            Course.objects.count(),
            CourseUnit.objects.count(),
            Lesson.objects.count(),
            LessonQuiz.objects.count(),
            LessonQuestion.objects.count(),
            Book.objects.count(),
            Chapter.objects.count(),
            ComprehensionQuestion.objects.count(),
        )
        _seed()  # second run
        _seed()  # third run
        after_counts = (
            Course.objects.count(),
            CourseUnit.objects.count(),
            Lesson.objects.count(),
            LessonQuiz.objects.count(),
            LessonQuestion.objects.count(),
            Book.objects.count(),
            Chapter.objects.count(),
            ComprehensionQuestion.objects.count(),
        )
        self.assertEqual(before_counts, after_counts)

    # ---- 12 ----
    def test_a0_and_a1_courses_are_free_or_demo_if_supported(self):
        for code in ("A0", "A1"):
            course = Course.objects.get(level__code=code)
            self.assertTrue(
                course.is_free,
                f"{code} course should be free; got is_free={course.is_free}",
            )
        # And the paid ones are NOT free.
        for code in ("A2", "B1", "B2", "C1", "C2"):
            course = Course.objects.get(level__code=code)
            self.assertFalse(course.is_free, f"{code} course should NOT be free")

    # ---- 13 ----
    def test_content_contains_arabic_and_english_versions(self):
        # At minimum, every lesson must have non-empty content_ar AND content_en
        # (or content_html). Sampling all is fast enough.
        for lesson in Lesson.objects.all():
            self.assertTrue(lesson.content_html.strip(), f"Lesson {lesson.pk} has empty content_html")
            self.assertTrue(lesson.content_ar.strip(), f"Lesson {lesson.pk} has empty content_ar")
            self.assertTrue(lesson.title_ar.strip(), f"Lesson {lesson.pk} has empty title_ar")
            self.assertTrue(lesson.title_en.strip(), f"Lesson {lesson.pk} has empty title_en")

    # ---- 14 ----
    def test_lesson_content_contains_ai_tutor_drill(self):
        """Every lesson must explicitly call out an AI Tutor Drill so the
        tutor knows what to do with the learner."""
        for lesson in Lesson.objects.all():
            self.assertIn(
                "AI Tutor Drill", lesson.content_html,
                f"Lesson {lesson.pk} missing AI Tutor Drill in English content",
            )
            self.assertIn(
                "المعلّم الذكي", lesson.content_ar,
                f"Lesson {lesson.pk} missing AI Tutor section in Arabic content",
            )
