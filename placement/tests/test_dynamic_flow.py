"""End-to-end view tests for the dynamic placement flow."""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from placement.models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementResult,
)
from learning_core.models import (
    LearningRecommendation, SkillMastery, StudentLearningProfile, UserWeakness,
)

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class DynamicPlacementFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user(
            username="flow@x.com", email="flow@x.com", password="pw",
        )
        self.client.login(username="flow@x.com", password="pw")

    def test_start_redirects_to_written_step(self):
        r = self.client.post(reverse("placement_start"))
        self.assertEqual(r.status_code, 302)
        attempt = PlacementAttempt.objects.get(user=self.user)
        self.assertRedirects(
            r, reverse("placement_written", args=[attempt.id]),
        )

    def test_written_page_renders_5_questions(self):
        r = self.client.post(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=self.user)
        page = self.client.get(reverse("placement_written", args=[attempt.id]))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.context["questions"]), 5)

    def test_speaking_page_renders_5_questions(self):
        self.client.post(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=self.user)
        written = PlacementAttemptQuestion.objects.filter(attempt=attempt, section="written")
        data = {
            f"q_{aq.id}": "I am learning English because I want better conversations."
            for aq in written
        }
        self.client.post(reverse("placement_written", args=[attempt.id]), data)

        page = self.client.get(reverse("placement_speaking", args=[attempt.id]))

        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.context["questions"]), 5)

    def test_written_submit_persists_answers(self):
        self.client.post(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=self.user)
        questions = list(
            PlacementAttemptQuestion.objects.filter(
                attempt=attempt, section="written",
            ).order_by("order")
        )
        # Build POST data; for MCQ questions, just send the first option.
        data = {}
        for aq in questions:
            if aq.question.expected_answer_type == "mcq" and aq.question.options:
                data[f"q_{aq.id}"] = aq.question.options[0]
            else:
                data[f"q_{aq.id}"] = "I am a student. I live in Cairo and I learn English every day."
        r = self.client.post(reverse("placement_written", args=[attempt.id]), data)
        self.assertRedirects(r, reverse("placement_speaking", args=[attempt.id]))

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "written_completed")
        for aq in PlacementAttemptQuestion.objects.filter(attempt=attempt, section="written"):
            self.assertTrue(aq.user_answer_text)

    def test_refresh_returns_same_questions(self):
        self.client.post(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=self.user)
        first = self.client.get(reverse("placement_written", args=[attempt.id]))
        second = self.client.get(reverse("placement_written", args=[attempt.id]))
        first_ids = [aq.question_id for aq in first.context["questions"]]
        second_ids = [aq.question_id for aq in second.context["questions"]]
        self.assertEqual(first_ids, second_ids,
                         "refresh must return the same questions, not re-randomise")

    def test_speaking_submit_finalises_with_ai_fallback(self):
        # Force the AI assess() to crash so we exercise the rule-based
        # fallback path.
        self.client.post(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=self.user)
        # Fill all written answers
        wq = PlacementAttemptQuestion.objects.filter(attempt=attempt, section="written")
        for aq in wq:
            aq.user_answer_text = ("Hello my name is Sara. I live in Cairo. "
                                   "I am learning English every day.")
            aq.save(update_fields=["user_answer_text"])
        # Speaking transcripts via the speaking POST
        sq = list(PlacementAttemptQuestion.objects.filter(attempt=attempt, section="speaking"))
        data = {}
        for aq in sq:
            data[f"q_{aq.id}_transcript"] = "My name is Sara and I am learning English."

        with patch("placement.views.assess", side_effect=RuntimeError("boom")):
            r = self.client.post(reverse("placement_speaking", args=[attempt.id]), data)
        self.assertRedirects(r, reverse("placement_result", args=[attempt.id]))

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, "completed")
        self.assertTrue(attempt.recommended_cefr_level)
        self.assertIsNotNone(attempt.completed_at)
        self.assertTrue(PlacementResult.objects.filter(user=self.user).exists())
        self.assertEqual(
            PlacementAttemptQuestion.objects.filter(attempt=attempt, score__isnull=False).count(),
            10,
        )
        self.assertEqual(
            PlacementAttemptQuestion.objects.filter(attempt=attempt, completed_at__isnull=False).count(),
            10,
        )
        result = PlacementResult.objects.get(user=self.user)
        self.assertEqual(result.transcript["mode"], "dynamic")
        self.assertEqual(len(result.transcript["written"]), 5)
        self.assertEqual(len(result.transcript["speaking"]), 5)
        self.assertIsNotNone(result.grammar_score)
        self.assertIsNotNone(result.vocabulary_score)
        self.assertIsNotNone(result.fluency_score)
        self.assertIsNone(result.pronunciation_score)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.cefr_level, attempt.recommended_cefr_level)
        self.assertEqual(self.user.profile.initial_cefr_level, attempt.recommended_cefr_level)
        self.assertTrue(self.user.profile.placement_completed)
        self.assertTrue(StudentLearningProfile.objects.filter(user=self.user).exists())
        self.assertTrue(SkillMastery.objects.filter(user=self.user).exists())
        self.assertTrue(UserWeakness.objects.filter(user=self.user).exists())
        self.assertTrue(LearningRecommendation.objects.filter(user=self.user).exists())

    def test_dynamic_assessor_payload_includes_all_attempt_questions(self):
        self.client.post(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=self.user)

        wq = list(
            PlacementAttemptQuestion.objects.filter(
                attempt=attempt, section="written",
            ).order_by("order")
        )
        wd = {}
        for index, aq in enumerate(wq, start=1):
            wd[f"q_{aq.id}"] = f"Written answer number {index}. I am adding enough words for scoring."
        self.client.post(reverse("placement_written", args=[attempt.id]), wd)

        sq = list(
            PlacementAttemptQuestion.objects.filter(
                attempt=attempt, section="speaking",
            ).order_by("order")
        )
        sd = {
            f"q_{aq.id}_transcript": f"Speaking answer number {index}. I am learning English for work."
            for index, aq in enumerate(sq, start=1)
        }

        captured = {}

        def fake_assess(payload):
            captured["payload"] = payload
            question_scores = []
            for item in payload["items"]:
                score = 61 if item["section"] == "written" else 58
                question_scores.append({
                    "attempt_question_id": item["attempt_question_id"],
                    "score": score,
                    "skill_score": score,
                    "grammar_score": score,
                    "vocabulary_score": score,
                    "fluency_score": score if item["section"] == "speaking" else None,
                    "feedback": "Dynamic scoring complete.",
                    "error_analysis": {"source": "test"},
                })
            return {
                "level": "B1",
                "written_score": 61,
                "speaking_score": 58,
                "feedback": "Dynamic scoring complete.",
                "question_scores": question_scores,
            }

        with patch("placement.views.assess", side_effect=fake_assess):
            self.client.post(reverse("placement_speaking", args=[attempt.id]), sd)

        items = captured["payload"]["items"]
        self.assertEqual(len(items), 10)
        written_items = [item for item in items if item["section"] == "written"]
        speaking_items = [item for item in items if item["section"] == "speaking"]
        self.assertEqual(len(written_items), 5)
        self.assertEqual(len(speaking_items), 5)
        self.assertIn("Written answer number 5", written_items[-1]["answer"])

        attempt.refresh_from_db()
        self.assertEqual(attempt.written_score, 61)
        self.assertEqual(attempt.speaking_score, 58)

    def test_other_user_cannot_access_attempt(self):
        self.client.post(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=self.user)
        other = User.objects.create_user(username="other@x.com", password="pw")
        self.client.logout()
        self.client.login(username="other@x.com", password="pw")
        r = self.client.get(reverse("placement_written", args=[attempt.id]))
        self.assertEqual(r.status_code, 404)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        r = self.client.post(reverse("placement_start"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/auth", r["Location"])

    def test_result_page_shows_level(self):
        # Walk the full happy path.
        self.client.post(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=self.user)
        wq = PlacementAttemptQuestion.objects.filter(attempt=attempt, section="written")
        wd = {}
        for aq in wq:
            if aq.question.expected_answer_type == "mcq" and aq.question.options:
                wd[f"q_{aq.id}"] = aq.question.options[0]
            else:
                wd[f"q_{aq.id}"] = "Yesterday I went to the park with my friends."
        self.client.post(reverse("placement_written", args=[attempt.id]), wd)
        sq = list(PlacementAttemptQuestion.objects.filter(attempt=attempt, section="speaking"))
        sd = {}
        for aq in sq:
            sd[f"q_{aq.id}_transcript"] = "I am Sara from Egypt and I love English."
        with patch("placement.views.assess", side_effect=RuntimeError("boom")):
            self.client.post(reverse("placement_speaking", args=[attempt.id]), sd)

        page = self.client.get(reverse("placement_result", args=[attempt.id]))
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        # The level badge appears in the rendered HTML.
        attempt.refresh_from_db()
        self.assertIn(attempt.recommended_cefr_level, body)
