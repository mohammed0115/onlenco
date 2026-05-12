"""Tests for the import_a0_curriculum management command."""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from daily_learning.services import a0_templates


class ImportA0CurriculumTests(TestCase):
    def test_creates_courselevel_courses_and_lessons(self):
        from courses.models import Course, CourseLevel, Lesson
        from tutor.models import AITutorPrompt

        out = StringIO()
        call_command("import_a0_curriculum", stdout=out)

        # 1 CourseLevel
        self.assertTrue(CourseLevel.objects.filter(code="A0").exists())
        # 5 courses (one per unit)
        self.assertEqual(
            Course.objects.filter(slug__startswith="a0-unit-").count(), 5,
            "Should create exactly 5 A0 unit courses",
        )
        # one Lesson per topic in the catalog
        self.assertEqual(
            Lesson.objects.filter(course__slug__startswith="a0-unit-").count(),
            len(a0_templates.A0_TOPICS),
            "Should create one Lesson per A0 topic",
        )
        # one AITutorPrompt per topic with a speaking item
        speaking_topics = [
            t for t in a0_templates.A0_TOPICS
            if any(i.item_type == "speaking" for i in t.items)
        ]
        self.assertEqual(
            AITutorPrompt.objects.filter(cefr_level="A0").count(),
            len(speaking_topics),
        )

    def test_rerun_is_idempotent_no_duplicates(self):
        from courses.models import Course, Lesson
        call_command("import_a0_curriculum", stdout=StringIO())
        first_lessons = Lesson.objects.count()
        first_courses = Course.objects.count()
        call_command("import_a0_curriculum", stdout=StringIO())
        self.assertEqual(Lesson.objects.count(), first_lessons,
                         "Rerunning must not create duplicate lessons")
        self.assertEqual(Course.objects.count(), first_courses,
                         "Rerunning must not create duplicate courses")

    def test_dry_run_writes_nothing(self):
        from courses.models import Course
        before = Course.objects.count()
        out = StringIO()
        call_command("import_a0_curriculum", "--dry-run", stdout=out)
        self.assertEqual(Course.objects.count(), before)
        self.assertIn("[DRY RUN]", out.getvalue())

    def test_each_lesson_has_a_quiz_with_one_question(self):
        from courses.models import Lesson, LessonQuestion, LessonQuiz
        call_command("import_a0_curriculum", stdout=StringIO())
        for lesson in Lesson.objects.filter(course__slug__startswith="a0-unit-"):
            self.assertTrue(
                LessonQuiz.objects.filter(lesson=lesson).exists(),
                f"Lesson {lesson.id} should have a quiz",
            )
            quiz = LessonQuiz.objects.get(lesson=lesson)
            self.assertGreaterEqual(
                LessonQuestion.objects.filter(quiz=quiz).count(), 1,
            )

    def test_tutor_prompt_correction_strategy_is_a0_friendly(self):
        from tutor.models import AITutorPrompt
        call_command("import_a0_curriculum", stdout=StringIO())
        # No A0 prompt should use a "Quick fix:" strategy.
        bad = AITutorPrompt.objects.filter(
            cefr_level="A0", correction_strategy="quick-fix-with-why",
        )
        self.assertEqual(bad.count(), 0,
                         "A0 tutor prompts must use gentle echo correction")


class AITutorPromptModelTests(TestCase):
    def test_default_correction_strategy_is_echo(self):
        from tutor.models import AITutorPrompt
        prompt = AITutorPrompt.objects.create(
            cefr_level="A0",
            prompt_en="Say: hello",
            prompt_ar="قل: hello",
        )
        self.assertEqual(prompt.correction_strategy, "echo-and-encourage")

    def test_lesson_slug_optional(self):
        from tutor.models import AITutorPrompt
        prompt = AITutorPrompt.objects.create(
            cefr_level="A0",
            prompt_en="Say: hi",
            prompt_ar="قل: hi",
        )
        self.assertEqual(prompt.lesson_slug, "")
        self.assertIsNone(prompt.lesson)
