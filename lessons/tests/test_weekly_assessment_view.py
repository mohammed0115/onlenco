"""Tests for the exam player (Duolingo-style) — replaces the old
server-rendered weekly_assessment view tests.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from learning_core.models import AdaptiveExercise, WeeklyAssessment

User = get_user_model()


class ExamPlayerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wv", password="pw")
        self.client.force_login(self.user)
        self.assessment = WeeklyAssessment.objects.create(
            user=self.user, kind="weekly",
            triggered_after_lessons_count=3, status="pending",
        )
        self.ex1 = AdaptiveExercise.objects.create(
            cefr_level="A2", difficulty_score=0.4, question_type="multiple_choice",
            question="She ___ to school every day.",
            options=["go", "goes"], correct_answer="goes",
        )
        self.ex2 = AdaptiveExercise.objects.create(
            cefr_level="A2", difficulty_score=0.4, question_type="fill_blank",
            question="Yesterday I ___ (eat) breakfast.",
            options=[], correct_answer="ate",
        )
        self.assessment.exercises.set([self.ex1, self.ex2])

    def test_legacy_weekly_url_redirects_to_player(self):
        r = self.client.get(reverse("weekly_assessment", args=[self.assessment.id]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("exam_play", args=[self.assessment.id]))

    def test_player_renders_questions_in_json(self):
        r = self.client.get(reverse("exam_play", args=[self.assessment.id]))
        self.assertEqual(r.status_code, 200)
        # The exercises payload is embedded in a <script type="application/json"> tag
        self.assertContains(r, "She ___ to school every day.")
        self.assertContains(r, "Yesterday I ___")
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, "in_progress")

    def test_player_post_grades_and_returns_json(self):
        r = self.client.post(
            reverse("exam_play", args=[self.assessment.id]),
            data=json.dumps({"answers": [
                {"exercise_id": self.ex1.id, "answer": "goes"},
                {"exercise_id": self.ex2.id, "answer": "ate"},
            ]}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["correct"], 2)
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["score"], 100.0)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, "completed")

    def test_player_partial_score(self):
        r = self.client.post(
            reverse("exam_play", args=[self.assessment.id]),
            data=json.dumps({"answers": [
                {"exercise_id": self.ex1.id, "answer": "goes"},
                {"exercise_id": self.ex2.id, "answer": "wrong"},
            ]}),
            content_type="application/json",
        )
        body = r.json()
        self.assertEqual(body["correct"], 1)
        self.assertEqual(body["score"], 50.0)

    def test_other_users_assessment_404(self):
        other = User.objects.create_user(username="other", password="pw")
        self.client.force_login(other)
        r = self.client.get(reverse("exam_play", args=[self.assessment.id]))
        self.assertEqual(r.status_code, 404)


class DailyExamTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dx", password="pw")
        self.client.force_login(self.user)

    def test_daily_exam_creates_assessment_and_redirects(self):
        r = self.client.get(reverse("exam_daily"))
        self.assertEqual(r.status_code, 302)
        wa = WeeklyAssessment.objects.filter(user=self.user, kind="daily").first()
        self.assertIsNotNone(wa)
        self.assertIn(f"/exam/{wa.id}/", r.url)

    def test_daily_exam_is_idempotent_within_a_day(self):
        r1 = self.client.get(reverse("exam_daily"))
        wa_id_1 = WeeklyAssessment.objects.filter(user=self.user, kind="daily").first().id
        r2 = self.client.get(reverse("exam_daily"))
        wa_id_2 = WeeklyAssessment.objects.filter(user=self.user, kind="daily").last().id
        self.assertEqual(wa_id_1, wa_id_2)
        self.assertEqual(WeeklyAssessment.objects.filter(user=self.user, kind="daily").count(), 1)

    def test_result_page_renders(self):
        from learning_core.services.weekly_assessment import complete, start_daily_assessment
        wa = start_daily_assessment(self.user)
        complete(wa, score=80.0)
        # Use the lessons-specific URL name. Previously this test
        # reversed `exam_result` which collided with the exams app's URL
        # of the same name and resolved to a 404 against an ExamAttempt id.
        r = self.client.get(reverse("lesson_exam_result", args=[wa.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "80")
