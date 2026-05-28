"""Coverage for the Onlenco Beginner Quiz Bank seed command."""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from courses.models import (
    Course, Lesson, LessonQuestion, LessonQuiz, QuestionMedia,
)


COURSE_SLUG = "onlenco-beginner"


class OnlencoBeginnerQuizBankTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet", stdout=StringIO())
        call_command("seed_onlenco_beginner_quiz_bank", "--quiet", stdout=StringIO())

    def _course_lessons(self):
        course = Course.objects.get(slug=COURSE_SLUG)
        return Lesson.objects.filter(course=course)

    def test_each_learning_unit_has_quiz(self):
        for lesson in self._course_lessons():
            self.assertTrue(
                LessonQuiz.objects.filter(lesson=lesson).exists(),
                f"Lesson {lesson.order} has no quiz",
            )

    def test_each_quiz_has_8_to_12_questions(self):
        for lesson in self._course_lessons():
            quiz = lesson.quiz
            n = quiz.questions.count()
            self.assertGreaterEqual(n, 8, f"Quiz for L{lesson.order} has only {n} questions")
            self.assertLessEqual(n, 12, f"Quiz for L{lesson.order} has {n} > 12 questions")

    def test_each_quiz_has_vocabulary_questions(self):
        for lesson in self._course_lessons():
            qs = lesson.quiz.questions.all()
            # First 3 questions are vocabulary by convention.
            self.assertGreaterEqual(
                qs.filter(order__lte=3).count(), 3,
                f"L{lesson.order} should have 3 vocab questions in orders 1-3",
            )

    def test_each_quiz_has_grammar_questions(self):
        for lesson in self._course_lessons():
            qs = lesson.quiz.questions.filter(order__gte=4, order__lte=6)
            self.assertEqual(
                qs.count(), 3,
                f"L{lesson.order} should have 3 grammar questions in orders 4-6",
            )

    def test_each_quiz_has_speaking_prompt(self):
        for lesson in self._course_lessons():
            speaking = lesson.quiz.questions.filter(
                question_type="speaking_prompt",
            )
            self.assertEqual(
                speaking.count(), 1,
                f"L{lesson.order} should have exactly 1 speaking_prompt question",
            )

    def test_each_quiz_has_listening_placeholder(self):
        for lesson in self._course_lessons():
            listening_qs = lesson.quiz.questions.filter(order=9)
            self.assertEqual(
                listening_qs.count(), 1,
                f"L{lesson.order} should have 1 listening question at order 9",
            )
            q = listening_qs.first()
            # Audio placeholder via QuestionMedia
            audio_media = QuestionMedia.objects.filter(
                question=q, media_type="audio",
            )
            self.assertEqual(audio_media.count(), 1)
            am = audio_media.first()
            # Placeholder = no file yet, but transcript + prompt are present.
            self.assertFalse(am.file)
            self.assertTrue(am.transcript)
            self.assertIn("American English", am.generation_prompt)

    def test_questions_have_arabic_and_english(self):
        for lesson in self._course_lessons():
            for q in lesson.quiz.questions.all():
                self.assertTrue(
                    q.question_text_en.strip(),
                    f"L{lesson.order} Q{q.order} missing English text",
                )
                self.assertTrue(
                    q.question_text_ar.strip(),
                    f"L{lesson.order} Q{q.order} missing Arabic text",
                )

    def test_seed_quiz_is_idempotent(self):
        before = LessonQuestion.objects.count()
        call_command("seed_onlenco_beginner_quiz_bank", "--quiet", stdout=StringIO())
        after = LessonQuestion.objects.count()
        self.assertEqual(before, after, "Quiz seed not idempotent — count changed")

    def test_no_copied_pdf_questions(self):
        """No EFE character names appear in any question."""
        import re
        forbidden = ["Lyla", "Pablo", "Mary", "Sarah", "Bruno", "Leesa",
                     "Una", "Robbie", "Ginger", "Lizzie", "Felix", "Coco", "Milo"]
        patterns = [re.compile(rf"\b{re.escape(n)}\b") for n in forbidden]
        for q in LessonQuestion.objects.all():
            for blob in (q.question_text_en, q.question_text_ar,
                         q.correct_answer, q.explanation):
                for pat in patterns:
                    self.assertIsNone(
                        pat.search(blob or ""),
                        f"Forbidden EFE name in Q{q.id}: {blob[:80]}",
                    )

    def test_questions_have_skill_in_explanation(self):
        """The skill metadata travels in the question's explanation (the
        LessonQuestion model has no `skill` column itself)."""
        for lesson in self._course_lessons():
            speaking = lesson.quiz.questions.filter(
                question_type="speaking_prompt",
            ).first()
            self.assertIsNotNone(speaking)
            self.assertIn("American", speaking.explanation)
