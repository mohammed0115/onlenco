"""Placement result correctness (reported bugs):

  1. The written score must reflect the answer sheet — not stay 0/100.
  2. The emailed result level must match the dashboard result level (the
     diagnostic email previously ran a separate assessor and disagreed,
     e.g. email B1 vs dashboard A2).
  3. The speaking result must show the student's spoken answer per question.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from placement.models import PlacementAttempt, PlacementResult
from placement.services.answer_key import correct_answer_for
from tutor.models import TutorMessage, VoiceCallEvaluation

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class PlacementResultFixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user(
            username="res@x.com", email="res@x.com", password="pw")
        self.client.login(username="res@x.com", password="pw")
        self.client.post(reverse("placement_start"))
        self.attempt = PlacementAttempt.objects.get(user=self.user)

    def _answer_written_correctly(self):
        rows = list(
            self.attempt.questions.filter(section="written")
            .select_related("question").order_by("order")
        )
        data = {}
        for aq in rows:
            data[f"q_{aq.id}"] = correct_answer_for(
                options=aq.question.options, rubric=aq.question.scoring_rubric,
                expected_type=aq.question.expected_answer_type,
            )
        # follow=True so the handoff redirect runs and creates the
        # placement voice conversation (as a real browser would).
        self.client.post(reverse("placement_written", args=[self.attempt.id]), data, follow=True)

    def test_written_score_reflects_correct_sheet(self):
        self._answer_written_correctly()
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.written_score, 100)
        # Every written question carries a per-question score now.
        self.assertEqual(
            self.attempt.questions.filter(section="written", score__isnull=False).count(), 5
        )

    def _finalise_voice(self, *, level="A2", overall=47):
        self._answer_written_correctly()
        self.attempt.refresh_from_db()
        conv = self.attempt.voice_conversation
        self.assertIsNotNone(conv)  # the written POST hands off + creates it
        # Simulate the spoken answers (one user turn per question, in order).
        answers = ["My name is Sara", "I am twenty years old",
                   "I am from Sudan", "I am a student", "to get a better job"]
        for a in answers:
            TutorMessage.objects.create(conversation=conv, role="user", content=a)
        VoiceCallEvaluation.objects.create(
            conversation=conv, cefr_level=level, overall_score=overall,
            fluency_score=overall, vocabulary_score=overall, grammar_score=overall,
            summary="Good effort.", word_count=25, turns_count=5, seconds=120,
        )
        with patch("placement.views.build_diagnostic_profile") as mock_diag:
            r = self.client.get(reverse("placement_voice_finalise", args=[self.attempt.id]))
        return r, mock_diag

    def test_dashboard_and_email_level_match(self):
        r, mock_diag = self._finalise_voice(level="A2", overall=47)
        self.assertRedirects(r, reverse("placement_result", args=[self.attempt.id]))
        # The result (dashboard) level.
        result = PlacementResult.objects.filter(user=self.user).latest("created_at")
        self.assertEqual(result.level, "A2")
        self.assertEqual(result.written_score, 100)          # not 0 anymore
        # The diagnostic/email got the SAME level + written score.
        self.assertTrue(mock_diag.called)
        assessment = mock_diag.call_args.kwargs["assessment"]
        self.assertEqual(assessment["level"], "A2")
        self.assertEqual(assessment["written_score"], 100)

    def test_speaking_answers_are_recorded(self):
        self._finalise_voice()
        rows = list(self.attempt.questions.filter(section="speaking").order_by("order"))
        # The student's spoken answers are now attached to the questions.
        self.assertEqual(rows[0].transcript, "My name is Sara")
        self.assertEqual(rows[2].transcript, "I am from Sudan")
        self.assertTrue(all((aq.transcript or "").strip() for aq in rows))
        self.assertTrue(all(aq.score is not None for aq in rows))

    def test_overall_blends_written_and_speaking(self):
        self._finalise_voice(level="A2", overall=47)
        self.attempt.refresh_from_db()
        # (100 written + 47 speaking) / 2 = 73 (rounded).
        self.assertEqual(self.attempt.overall_score, 74)

    def test_recompute_command_fixes_stale_result(self):
        self._finalise_voice(level="A2", overall=47)
        # Simulate an OLD attempt stored with a wrong 0 written score.
        self.attempt.refresh_from_db()
        result = self.attempt.result
        PlacementAttempt.objects.filter(pk=self.attempt.id).update(
            written_score=0, overall_score=23)
        PlacementResult.objects.filter(pk=result.id).update(
            written_score=0, overall_score=23)
        call_command("recompute_placement_results", attempt=self.attempt.id,
                     stdout=StringIO())
        self.attempt.refresh_from_db()
        result.refresh_from_db()
        self.assertEqual(self.attempt.written_score, 100)
        self.assertEqual(self.attempt.overall_score, 74)
        self.assertEqual(result.written_score, 100)
        self.assertEqual(result.overall_score, 74)
