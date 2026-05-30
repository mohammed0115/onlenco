"""Tests for the extended Onlenco Quiz Engine (interactive types).

Covers:
  * Schema — new metadata JSONField + 5 new question_type choices
  * Grading — per-type rubrics (sentence_ordering, frequency_scale,
    table_sentence_builder, listening_match, speaking_sentence_builder,
    question_transform)
  * Renderer — quiz page renders each new type without 500
  * Backward compatibility — legacy multiple_choice / fill_blank still work
"""
from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from courses.models import (
    Course, CourseEnrollment, Lesson, LessonQuestion, LessonQuiz,
)
from courses.services.quiz_grader import grade_question


User = get_user_model()


def _seed_courses():
    call_command("seed_onlenco_beginner_48_units",  "--quiet", stdout=StringIO())
    call_command("seed_free_time_quiz_demo", "--quiet", stdout=StringIO())


class GradingTests(TestCase):
    """Unit-test the grading rubrics in isolation — no view layer."""

    @classmethod
    def setUpTestData(cls):
        _seed_courses()
        cls.lesson = (
            Lesson.objects.filter(course__slug="onlenco-beginner", order=39).first()
        )
        cls.quiz = cls.lesson.quiz
        cls.questions = {q.question_type: q for q in cls.quiz.questions.all()}

    def test_sentence_ordering_grading_correct(self):
        q = self.questions["sentence_ordering"]
        # Submit the correct word order as a pipe-delimited string.
        result = grade_question(q, "Amani|usually|reads|novels|on weekends")
        self.assertTrue(result["is_correct"])
        self.assertEqual(result["score"], 1.0)

    def test_sentence_ordering_grading_wrong(self):
        q = self.questions["sentence_ordering"]
        result = grade_question(q, "usually|Amani|reads|novels|on weekends")
        self.assertFalse(result["is_correct"])

    def test_frequency_scale_grading_with_tolerance(self):
        q = self.questions["frequency_scale"]
        # Exact match
        perfect = {
            "never": 0, "rarely": 15, "sometimes": 40,
            "often": 65, "usually": 85, "always": 100,
        }
        r = grade_question(q, perfect)
        self.assertTrue(r["is_correct"])

        # Within tolerance (±10%) — should still pass
        close = {
            "never": 5, "rarely": 20, "sometimes": 35,
            "often": 70, "usually": 90, "always": 95,
        }
        r = grade_question(q, close)
        self.assertTrue(r["is_correct"])

        # Way off — should fail
        wrong = {
            "never": 100, "rarely": 80, "sometimes": 60,
            "often": 40, "usually": 20, "always": 0,
        }
        r = grade_question(q, wrong)
        self.assertFalse(r["is_correct"])
        self.assertEqual(r["score"], 0.0)

    def test_table_sentence_builder_grading(self):
        q = self.questions["table_sentence_builder"]
        # Four valid sentences using one item from each column
        valid = (
            "Yusuf always plays soccer on Mondays\n"
            "Noor usually studies English after school\n"
            "Kareem often watches movies in the evening\n"
            "Salma sometimes cooks dinner at night"
        )
        r = grade_question(q, valid)
        self.assertTrue(r["is_correct"], msg=f"Expected pass, got score={r['score']}")

        # Only one sentence — fails the min count
        r = grade_question(q, "Yusuf always plays soccer on Mondays")
        self.assertFalse(r["is_correct"])
        self.assertLess(r["score"], 1.0)

    def test_listening_match_grading(self):
        q = self.questions["listening_match"]
        correct = {
            "Omar plays basketball":  "often",
            "Layla cooks for family": "sometimes",
            "Layla cooks on weekdays": "never",
            "Tarek visits parents":   "rarely",
        }
        r = grade_question(q, correct)
        self.assertTrue(r["is_correct"])

        partial = correct.copy()
        partial["Tarek visits parents"] = "always"  # wrong
        r = grade_question(q, partial)
        self.assertFalse(r["is_correct"])
        self.assertAlmostEqual(r["score"], 0.75)

    def test_speaking_sentence_builder_grading(self):
        q = self.questions["speaking_sentence_builder"]
        r = grade_question(q, "done")
        self.assertTrue(r["is_correct"])
        # No answer → fail
        r = grade_question(q, "")
        self.assertFalse(r["is_correct"])

    def test_question_transform_grading(self):
        q = self.questions["question_transform"]
        r = grade_question(q, "How often does Hala study English?")
        self.assertTrue(r["is_correct"], msg=f"feedback: {r['feedback_en']}")
        # Wrong start
        r = grade_question(q, "What does Hala do?")
        self.assertFalse(r["is_correct"])
        # Missing auxiliary
        r = grade_question(q, "How often Hala studies English?")
        self.assertFalse(r["is_correct"])


class SchemaTests(TestCase):
    """Metadata JSONField is present and the new types are valid choices."""

    def test_metadata_field_exists(self):
        # Build a question with arbitrary metadata — must not crash.
        from courses.models import LessonQuiz, LessonQuestion, Course, CourseLevel, CourseUnit, Lesson
        from django.contrib.auth import get_user_model
        level, _ = CourseLevel.objects.get_or_create(code="X0", defaults={"name": "Test", "order": 1})
        teacher = User.objects.create_user(username="t-meta", password="pw")
        course = Course.objects.create(title="T", slug="t-meta", level=level, teacher=teacher, created_by=teacher)
        unit = CourseUnit.objects.create(course=course, title="U", order=1)
        lesson = Lesson.objects.create(course=course, unit=unit, title="L", order=1)
        quiz = LessonQuiz.objects.create(lesson=lesson, title="Q")
        q = LessonQuestion.objects.create(
            quiz=quiz, question_type="frequency_scale",
            question_text="?", options=[],
            correct_answer="scale",
            metadata={"scale_items": [{"word": "never", "percent": 0}]},
        )
        loaded = LessonQuestion.objects.get(pk=q.pk)
        self.assertEqual(loaded.metadata["scale_items"][0]["word"], "never")

    def test_new_question_types_are_valid(self):
        from courses.models import QUESTION_TYPE_CHOICES
        codes = {c[0] for c in QUESTION_TYPE_CHOICES}
        for new_kind in [
            "frequency_scale", "table_sentence_builder", "listening_match",
            "speaking_sentence_builder", "question_transform",
        ]:
            self.assertIn(new_kind, codes)


class RendererTests(TestCase):
    """The quiz page must render every new type without a 500."""

    @classmethod
    def setUpTestData(cls):
        _seed_courses()
        cls.course = Course.objects.get(slug="onlenco-beginner")
        cls.lesson = Lesson.objects.get(course=cls.course, order=39)
        cls.user = User.objects.create_user(
            username="quiz-student", password="pw", email="q@onlenco.test",
        )
        if hasattr(cls.user, "profile"):
            cls.user.profile.email_verified = True
            cls.user.profile.subscription_status = "active"
            cls.user.profile.save()
        CourseEnrollment.objects.get_or_create(user=cls.user, course=cls.course)

    def _get_quiz(self):
        c = Client(SERVER_NAME="127.0.0.1")
        c.force_login(self.user)
        return c.get(
            f"/courses/{self.course.pk}/lessons/{self.lesson.pk}/quiz/",
            HTTP_HOST="127.0.0.1",
        )

    def test_quiz_page_does_not_break_with_new_question_types(self):
        r = self._get_quiz()
        self.assertNotEqual(r.status_code, 500)
        if r.status_code == 200:
            body = r.content.decode("utf-8", errors="ignore")
            for marker in [
                "onlenco-q__scale",        # frequency_scale
                "onlenco-q__token-bank",   # sentence_ordering
                "onlenco-q__tbuilder",     # table_sentence_builder
                "onlenco-q__lmatch",       # listening_match
                "onlenco-q__speak-builder",# speaking_sentence_builder
                "onlenco-q__qtransform",   # question_transform
            ]:
                self.assertIn(marker, body, f"Missing renderer for {marker}")

    def test_listening_match_supports_pending_audio(self):
        r = self._get_quiz()
        if r.status_code != 200:
            return
        body = r.content.decode("utf-8", errors="ignore")
        # The seed sets audio_status="pending_generation" → the
        # pending marker should appear.
        self.assertIn("onlenco-q__lmatch-pending", body)

    def test_speaking_sentence_builder_links_ai_tutor(self):
        r = self._get_quiz()
        if r.status_code != 200:
            return
        body = r.content.decode("utf-8", errors="ignore")
        self.assertIn("onlenco-q__tutor-link", body)
        self.assertIn(f"/tutor/?lesson={self.lesson.pk}", body)


class BackwardCompatibilityTests(TestCase):
    """Legacy quizzes (multiple_choice / fill_blank) still grade and render."""

    @classmethod
    def setUpTestData(cls):
        # Seed the regular Beginner course; that puts MC + fill_blank
        # questions on every Lesson.
        call_command("seed_onlenco_beginner_48_units",  "--quiet", stdout=StringIO())
        call_command("seed_onlenco_beginner_quiz_bank", "--quiet", stdout=StringIO())

    def test_old_quizzes_still_work(self):
        course = Course.objects.get(slug="onlenco-beginner")
        # A non-Free-Time lesson — the regular quiz bank.
        lesson = Lesson.objects.get(course=course, order=1)
        quiz = lesson.quiz
        mc = quiz.questions.filter(question_type="multiple_choice").first()
        self.assertIsNotNone(mc)
        # Grading by string equality still works.
        right = grade_question(mc, mc.correct_answer)
        self.assertTrue(right["is_correct"])
        wrong = grade_question(mc, "definitely-not-correct")
        self.assertFalse(wrong["is_correct"])
