"""Coverage for `lesson_ai_context_builder.build_lesson_tutor_prompt`.

Verifies the tutor-prompt builder pulls real context from a seeded Lesson
and produces a scoped, beginner-friendly, single-lesson instruction.
"""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from courses.models import Course, Lesson
from tutor.services.lesson_ai_context_builder import (
    BEGINNER_STYLE_MARKERS, build_lesson_tutor_prompt,
)


COURSE_SLUG = "onlenco-beginner"


class LessonAITutorContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet", stdout=StringIO())
        cls.course = Course.objects.get(slug=COURSE_SLUG)
        cls.lesson_1 = Lesson.objects.get(course=cls.course, order=1)
        cls.lesson_10 = Lesson.objects.get(course=cls.course, order=10)

    def test_ai_tutor_receives_lesson_context(self):
        prompt = build_lesson_tutor_prompt(self.lesson_1)
        self.assertIn("Lesson context:", prompt)
        self.assertIn(self.lesson_1.title, prompt)
        self.assertIn(f"Unit:   {self.lesson_1.order}", prompt)

    def test_ai_tutor_prompt_contains_vocabulary(self):
        prompt = build_lesson_tutor_prompt(self.lesson_10)
        self.assertIn("Allowed vocabulary:", prompt)
        # Unit 10 covers workplaces — the seed put related vocab on the lesson.
        self.assertTrue(
            (self.lesson_10.vocabulary_topic and self.lesson_10.vocabulary_topic.split()[0] in prompt),
            "vocab cue from the lesson should appear in the prompt",
        )

    def test_ai_tutor_prompt_contains_grammar_focus(self):
        prompt = build_lesson_tutor_prompt(self.lesson_10)
        self.assertIn("New language:", prompt)

    def test_ai_tutor_uses_beginner_style(self):
        prompt = build_lesson_tutor_prompt(self.lesson_1)
        for marker in BEGINNER_STYLE_MARKERS:
            self.assertIn(
                marker, prompt,
                f"Expected beginner-style marker missing: {marker!r}",
            )

    def test_ai_tutor_does_not_start_general_chat(self):
        """The prompt must contain a scope-restriction (no off-topic chat)."""
        prompt = build_lesson_tutor_prompt(self.lesson_1)
        self.assertIn("stay with today's topic", prompt.lower())

    def test_ai_tutor_tracks_lesson_practice_completion(self):
        prompt = build_lesson_tutor_prompt(self.lesson_1)
        self.assertIn("Completion criteria:", prompt)
        self.assertIn("3 correct sentences", prompt)

    def test_ai_tutor_supports_arabic_explanation_when_needed(self):
        prompt = build_lesson_tutor_prompt(self.lesson_1)
        self.assertIn("Arabic support:", prompt)
        # Arabic hint is allowed only as a *short* fallback.
        self.assertIn("Arabic hint", prompt)

    def test_ai_tutor_personalises_with_student_name(self):
        prompt = build_lesson_tutor_prompt(self.lesson_1, student_name="Amani")
        self.assertIn("Amani", prompt)

    def test_ai_tutor_uses_cefr_override(self):
        prompt = build_lesson_tutor_prompt(self.lesson_1, cefr_override="A1")
        self.assertIn("Level:  A1", prompt)
