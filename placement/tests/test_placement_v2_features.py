"""Placement requirements doc — new pieces: configurable level mapping +
AI alternative-answer suggestions for oral guidance (never grading, never
charging AI-Tutor minutes)."""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from ai_usage import constants as C
from placement.models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementQuestion, PlacementResult,
)
from placement.services import ai_alternatives
from placement.services.level_mapping import level_for_percentage

User = get_user_model()


class LevelMappingTests(TestCase):
    def test_default_bands(self):
        self.assertEqual(level_for_percentage(10), "A0")
        self.assertEqual(level_for_percentage(30), "A1")
        self.assertEqual(level_for_percentage(50), "A2")
        self.assertEqual(level_for_percentage(70), "B1")
        self.assertEqual(level_for_percentage(80), "B2")
        self.assertEqual(level_for_percentage(92), "C1")
        self.assertEqual(level_for_percentage(99), "C2")

    def test_clamps_and_handles_bad_input(self):
        self.assertEqual(level_for_percentage(0), "A0")
        self.assertEqual(level_for_percentage(150), "C2")
        self.assertEqual(level_for_percentage(None), "A0")

    @override_settings(PLACEMENT_LEVEL_MAP=[(50, "A1"), (100, "C1")])
    def test_configurable(self):
        self.assertEqual(level_for_percentage(40), "A1")
        self.assertEqual(level_for_percentage(60), "C1")


class AIAlternativesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def test_starter_questions_need_no_ai_call(self):
        q = PlacementQuestion.objects.get(code="sp.v2.003")  # "Where are you from?"
        with patch("ai_usage.services.ai_client.complete_text") as mock_ai:
            alts = ai_alternatives.alternatives_for(q, generate=True)
        mock_ai.assert_not_called()
        self.assertGreaterEqual(len(alts), 3)
        # Frames, not fixed names/countries — "from" appears, "Egypt" never.
        self.assertTrue(any("from" in a.lower() for a in alts))
        joined = " ".join(alts)
        self.assertNotIn("Egypt", joined)
        self.assertNotIn("John", joined)

    def test_custom_question_generates_and_caches(self):
        q = PlacementQuestion.objects.create(
            code="sp.custom.001", question_text="What is your favourite food?",
            question_type="speaking", skill="speaking", topic="hobby",
            expected_answer_type="voice", is_active=True,
        )
        with patch("ai_usage.services.ai_client.complete_text",
                   return_value='{"alternatives": ["Pizza.", "I love pasta.", "Rice."]}') as mock_ai:
            alts = ai_alternatives.ensure_alternatives(q)
        # Called through the wrapper with the placement feature and WITHOUT
        # enforcing AI-Tutor minutes.
        self.assertEqual(alts, ["Pizza.", "I love pasta.", "Rice."])
        kwargs = mock_ai.call_args.kwargs
        self.assertEqual(kwargs.get("feature"), C.FEATURE_PLACEMENT_ALTERNATIVES)
        self.assertEqual(kwargs.get("enforce_minutes"), False)
        # Cached → a second call makes no AI request.
        q.refresh_from_db()
        self.assertEqual(q.ai_alternatives, ["Pizza.", "I love pasta.", "Rice."])
        with patch("ai_usage.services.ai_client.complete_text") as mock2:
            again = ai_alternatives.alternatives_for(q, generate=True)
        mock2.assert_not_called()
        self.assertEqual(again, ["Pizza.", "I love pasta.", "Rice."])

    def test_generation_failure_is_graceful(self):
        q = PlacementQuestion.objects.create(
            code="sp.custom.002", question_text="Describe your week.",
            question_type="speaking", skill="speaking", topic="hobby",
            expected_answer_type="voice", is_active=True,
        )
        with patch("ai_usage.services.ai_client.complete_text",
                   side_effect=RuntimeError("boom")):
            alts = ai_alternatives.ensure_alternatives(q)
        self.assertEqual(alts, [])  # friendly fallback, no crash

    def test_alternatives_do_not_affect_grading(self):
        # alternatives_for is read-only on scores — it never touches aq.score.
        q = PlacementQuestion.objects.get(code="sp.v2.001")
        attempt = PlacementAttempt.objects.create(
            user=User.objects.create_user("g@x.com", "g@x.com", "pw"),
            status="completed",
        )
        aq = PlacementAttemptQuestion.objects.create(
            attempt=attempt, question=q, section="speaking", order=1,
            transcript="My name is Sam", score=70.0,
        )
        ai_alternatives.alternatives_for(q, student_transcript=aq.transcript)
        aq.refresh_from_db()
        self.assertEqual(aq.score, 70.0)


@override_settings(AXES_ENABLED=False)
class ResultPageAlternativesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user("rp@x.com", "rp@x.com", "pw")
        self.client.force_login(self.user)

    def test_result_page_shows_other_possible_answers(self):
        result = PlacementResult.objects.create(user=self.user, level="A2")
        attempt = PlacementAttempt.objects.create(
            user=self.user, status="completed", written_score=80,
            speaking_score=60, overall_score=70, recommended_cefr_level="A2",
            result=result,  # finalised → passes the strict gate
        )
        q = PlacementQuestion.objects.get(code="sp.v2.003")
        PlacementAttemptQuestion.objects.create(
            attempt=attempt, question=q, section="speaking", order=1,
            transcript="I am from Sudan", score=60.0,
        )
        resp = self.client.get(reverse("placement_result", args=[attempt.id]))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("إجابات أخرى مقترحة", body)        # bilingual label renders
        self.assertIn("I come from", body)               # a starter frame
        self.assertNotIn("Egypt", body)                  # no fixed country
        self.assertIn("لا تؤثّر على درجتك", body)        # guidance disclaimer
