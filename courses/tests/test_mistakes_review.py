"""Mistake review (spaced repetition) UI + the lesson finish → challenge wiring."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseLevel, Lesson, LessonQuestion, LessonQuiz
from learning_core.models import StudentMistake
from learning_core.services import mastery_service


User = get_user_model()


def _due_mistake(user, question, *, count=0):
    return StudentMistake.objects.create(
        user=user, question=question, user_answer="wrong",
        correct_answer="right", explanation_en="because", explanation_ar="لأن",
        review_count=count, mastered=False,
        next_review_at=timezone.now() - timedelta(hours=1),  # due
    )


class MistakeReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rev", password="pw")
        self.client.force_login(self.user)
        level = CourseLevel.objects.get_or_create(code="A0", defaults={"name": "B", "order": 0})[0]
        self.course = Course.objects.create(
            title="C", slug="rev-c", level=level, status="published", is_active=True, is_free=True)
        self.lesson = Lesson.objects.create(
            course=self.course, title="L", content_html="<p>x</p>",
            status="published", is_active=True, order=1, code="RVL1")
        self.quiz = LessonQuiz.objects.create(
            lesson=self.lesson, code="RVQ1", title="Q", title_ar="ا", title_en="Q")
        self.q = LessonQuestion.objects.create(
            quiz=self.quiz, order=0, question_type="tap_choice",
            question_text="What is hello?", question_text_ar="ما معنى hello؟",
            question_text_en="What is hello?", correct_answer="مرحبا",
            explanation="greeting", explanation_ar="تحية", explanation_en="greeting")

    def test_review_page_lists_due_mistakes(self):
        m = _due_mistake(self.user, self.q)
        r = self.client.get(reverse("courses:mistakes_review"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-mistake-id="%d"' % m.pk)  # a real card
        self.assertContains(r, "right")  # the correct answer is revealed in the card

    def test_review_page_empty_state(self):
        r = self.client.get(reverse("courses:mistakes_review"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "onlenco-review-empty")
        self.assertNotContains(r, 'data-mistake-id="')  # no cards rendered

    def test_record_got_it_reschedules_and_increments(self):
        m = _due_mistake(self.user, self.q, count=0)
        url = reverse("courses:mistakes_review_record", args=[m.pk])
        r = self.client.post(url, {"result": "got_it"})
        self.assertEqual(r.status_code, 200)
        m.refresh_from_db()
        self.assertEqual(m.review_count, 1)
        self.assertFalse(m.mastered)
        self.assertGreater(m.next_review_at, timezone.now())  # pushed out

    def test_three_clean_recalls_master_the_mistake(self):
        m = _due_mistake(self.user, self.q, count=2)  # next recall is the 3rd
        self.client.post(reverse("courses:mistakes_review_record", args=[m.pk]), {"result": "got_it"})
        m.refresh_from_db()
        self.assertTrue(m.mastered)

    def test_wrong_recall_brings_it_back_soon(self):
        m = _due_mistake(self.user, self.q, count=1)
        mastery_service.record_manual_review(m, correct=False)
        m.refresh_from_db()
        self.assertFalse(m.mastered)
        # back within a few hours, not days
        self.assertLess(m.next_review_at, timezone.now() + timedelta(hours=6))

    def test_cannot_record_another_users_mistake(self):
        other = User.objects.create_user(username="other", password="pw")
        m = _due_mistake(other, self.q)
        r = self.client.post(reverse("courses:mistakes_review_record", args=[m.pk]), {"result": "got_it"})
        self.assertEqual(r.status_code, 404)


class FinishStepUsesChallengeTests(TestCase):
    """The lesson finish step launches the Duolingo-style challenge."""

    @classmethod
    def setUpTestData(cls):
        from courses.models import CourseEnrollment
        from courses.tests.test_super_lesson_01 import (
            _get_lesson_quiz, _make_student, _seed_all,
        )
        _seed_all()
        cls.course, cls.lesson, _ = _get_lesson_quiz()
        cls.student = _make_student("finish-chal")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def test_finish_step_links_to_challenge_not_plain_quiz(self):
        from courses.tests.test_super_lesson_01 import _login
        url = reverse("courses:lesson_step", args=[self.course.pk, self.lesson.pk, "finish"])
        body = _login(self.student).get(url, HTTP_HOST="127.0.0.1").content.decode()
        challenge_url = reverse("courses:challenge_start", args=[self.course.pk, self.lesson.pk])
        self.assertIn(challenge_url, body)
