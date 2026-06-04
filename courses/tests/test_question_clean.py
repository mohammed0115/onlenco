"""LessonQuestion.clean() contract — aligned with the teacher quiz builder.

Open prompts (speaking/writing) are AI-graded and need no correct_answer; MCQ
types (the full set, not just the literal "multiple_choice") need options + a
correct answer among them. Guards against the form↔model mismatch a refactor
could reintroduce.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from courses.models import (
    Course, CourseLevel, Lesson, LessonQuestion, LessonQuiz,
)


class QuestionCleanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        level = CourseLevel.objects.create(code="A1", name="A1", order=1)
        course = Course.objects.create(title="C", slug="c", level=level)
        lesson = Lesson.objects.create(course=course, title="L", order=1, lesson_type="reading")
        cls.quiz = LessonQuiz.objects.create(lesson=lesson, title="Q")

    def _q(self, **kw):
        return LessonQuestion(quiz=self.quiz, question_text="Prompt?", question_text_en="Prompt?", order=1, **kw)

    def test_open_prompt_needs_no_correct_answer(self):
        self._q(question_type="speaking_prompt", correct_answer="").full_clean()  # must not raise
        self._q(question_type="writing_prompt", correct_answer="").full_clean()

    def test_non_open_type_still_requires_correct_answer(self):
        with self.assertRaises(ValidationError):
            self._q(question_type="fill_blank", correct_answer="").full_clean()

    def test_mcq_set_requires_options_beyond_literal_multiple_choice(self):
        # image_choice is an MCQ type → options rule must apply.
        with self.assertRaises(ValidationError):
            self._q(question_type="image_choice", correct_answer="A", options=["A"]).full_clean()

    def test_valid_mcq_passes(self):
        self._q(question_type="multiple_choice", correct_answer="A", options=["A", "B"]).full_clean()
