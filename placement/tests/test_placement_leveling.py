"""Score-based placement: the percentage score maps DIRECTLY to the CEFR
level (A0..C2) via PLACEMENT_LEVEL_MAP. No difficulty cap — 96/100 → C2.

The "score" measures answer correctness; the "final_level" is just that score
run through the percentage→CEFR mapping.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from placement.services.answer_key import correct_answer_for
from placement.services.level_mapping import level_for_percentage
from placement.services.placement_question_selector import create_placement_attempt
from tutor.models import TutorConversation, VoiceCallEvaluation

User = get_user_model()
NO_AI = patch("ai_usage.services.ai_client.complete_text", side_effect=RuntimeError("no-ai"))


class PercentageToLevelTests(TestCase):
    """The product mapping, exact band edges."""

    def test_band_edges(self):
        cases = {
            96: "C2", 100: "C2",
            95: "C1", 89: "C1",
            88: "B2", 76: "B2",
            75: "B1", 61: "B1",
            60: "A2", 41: "A2",
            40: "A1", 21: "A1",
            20: "A0", 0: "A0",
        }
        for pct, level in cases.items():
            self.assertEqual(level_for_percentage(pct), level, f"{pct} should be {level}")

    def test_high_score_reaches_c2_no_cap(self):
        # The reported bug: 96 must NOT be A2 — it is C2.
        self.assertEqual(level_for_percentage(96), "C2")
        self.assertNotEqual(level_for_percentage(96), "A2")


@override_settings(AXES_ENABLED=False)
class FinaliseLevelIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user("fi@x.com", "fi@x.com", "pw")
        self.client.force_login(self.user)
        self.attempt = create_placement_attempt(self.user)
        self.conv = TutorConversation.objects.create(user=self.user, topic="placement")
        self.attempt.voice_conversation = self.conv
        self.attempt.written_score = 100
        self.attempt.save(update_fields=["voice_conversation", "written_score"])
        live = {
            "What is your name?": "My name is Hazawu",
            "How old are you?": "I am 40 years old",
            "Where are you from?": "I am from Sudan",
            "What do you do for a living?": "I am a teacher",
            "Why do you want to learn English?": "Because I need it for my job",
        }
        for r in self.attempt.questions.filter(section="speaking").select_related("question"):
            r.transcript = live[r.question.question_text]
            r.save(update_fields=["transcript"])
        # Actually answer the written section correctly (grade_written_section
        # re-grades from the stored answer text, so set the right answers).
        for aq in self.attempt.questions.filter(section="written").select_related("question"):
            aq.user_answer_text = correct_answer_for(
                options=aq.question.options, rubric=aq.question.scoring_rubric,
                expected_type=aq.question.expected_answer_type,
            )
            aq.save(update_fields=["user_answer_text"])

    def test_final_level_follows_overall_score_no_cap(self):
        VoiceCallEvaluation.objects.create(
            conversation=self.conv, cefr_level="A2", overall_score=96,
            fluency_score=96, vocabulary_score=96, grammar_score=96,
            summary="ok", word_count=25, turns_count=5, seconds=120)
        with patch("placement.views.build_diagnostic_profile", return_value={}), NO_AI:
            r = self.client.get(reverse("placement_voice_finalise", args=[self.attempt.id]))
        self.assertRedirects(r, reverse("placement_result", args=[self.attempt.id]),
                             fetch_redirect_response=False)
        self.attempt.refresh_from_db()
        # The AI estimated A2, but the level is taken from the overall SCORE
        # (written 100 + speaking ~85 → ~92 → C1), with NO difficulty cap.
        self.assertEqual(
            self.attempt.recommended_cefr_level,
            level_for_percentage(self.attempt.overall_score),
        )
        self.assertGreaterEqual(self.attempt.speaking_score, 70)
        # A high score must NOT be pinned to A1/A2 anymore.
        self.assertNotIn(self.attempt.recommended_cefr_level, ("A0", "A1", "A2"))

    def test_result_page_shows_level_and_score_separately(self):
        VoiceCallEvaluation.objects.create(
            conversation=self.conv, cefr_level="A2", overall_score=96,
            summary="ok", word_count=25, turns_count=5, seconds=120)
        with patch("placement.views.build_diagnostic_profile", return_value={}), NO_AI:
            self.client.get(reverse("placement_voice_finalise", args=[self.attempt.id]))
        body = self.client.get(reverse("placement_result", args=[self.attempt.id])).content.decode()
        self.assertIn("مستوى التحدث", body)        # Speaking LEVEL label
        self.assertIn("المستوى النهائي", body)      # Final level label


class FillerScoringTests(TestCase):
    def test_filler_answer_is_not_perfect(self):
        from placement.services import speaking_eval
        with NO_AI:
            res = speaking_eval.score_speaking_answers([
                ("What is your name?",
                 "I'm not going to finish that one, I'm just going to say my name is Sam")])
        self.assertLessEqual(res[0]["score"], 85)
        self.assertTrue(res[0]["feedback"])
