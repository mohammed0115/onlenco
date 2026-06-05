"""Strict-but-safe speaking completion gate (final validation decision).

The final result + course require a COMPLETED speaking section; a missing /
empty / too-short / failed speaking call is retryable and never finalises.
An admin can override explicitly with a reason.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from placement.models import (
    PlacementAttempt, PlacementResult, PlacementSpeakingAttempt,
)
from placement.services import admin_override, speaking_quota
from placement.services.answer_key import correct_answer_for
from subscriptions.models import UserDailyQuota
from tutor.models import TutorMessage, VoiceCallEvaluation

User = get_user_model()

# Assistant prompt (must echo the question's keywords) + the student reply.
QPROMPTS = [
    ("What is your name?", "My name is Sara"),
    ("How old are you?", "I am twenty"),
    ("Where are you from?", "I am from Sudan"),
    ("What do you do for a living?", "I am a student"),
    ("Why do you want to learn English?", "to get a better job"),
]


@override_settings(AXES_ENABLED=False, PLACEMENT_REQUIRE_SPEAKING_FOR_FINAL_RESULT=True,
                   PLACEMENT_SPEAKING_MIN_ANSWERS=3)
class PlacementSpeakingGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user("gate@x.com", "gate@x.com", "pw")
        self.client.force_login(self.user)
        self.client.post(reverse("placement_start"))
        self.attempt = PlacementAttempt.objects.get(user=self.user)

    def _answer_written(self):
        rows = list(self.attempt.questions.filter(section="written").select_related("question"))
        data = {f"q_{aq.id}": correct_answer_for(
            options=aq.question.options, rubric=aq.question.scoring_rubric,
            expected_type=aq.question.expected_answer_type) for aq in rows}
        self.client.post(reverse("placement_written", args=[self.attempt.id]), data, follow=True)
        self.attempt.refresh_from_db()

    def _voice(self, n_answers, *, with_eval=True, tutor_questions=None):
        self.attempt.refresh_from_db()
        conv = self.attempt.voice_conversation
        tq = tutor_questions if tutor_questions is not None else n_answers
        TutorMessage.objects.create(conversation=conv, role="assistant", content="Hi, welcome.")
        for i in range(tq):
            q, a = QPROMPTS[i]
            TutorMessage.objects.create(conversation=conv, role="assistant", content=q)
            if i < n_answers:
                TutorMessage.objects.create(conversation=conv, role="user", content=a)
        if with_eval:
            VoiceCallEvaluation.objects.create(
                conversation=conv, cefr_level="A2", overall_score=55,
                fluency_score=55, vocabulary_score=55, grammar_score=55,
                summary="ok", word_count=20, turns_count=n_answers, seconds=90)
        with patch("placement.views.build_diagnostic_profile", return_value={}), \
             patch("ai_usage.services.ai_client.complete_text", side_effect=RuntimeError("no-ai")):
            return self.client.get(reverse("placement_voice_finalise", args=[self.attempt.id]))

    # ---- 1: written done, speaking missing → result blocked ----
    def test_result_blocked_when_speaking_missing(self):
        self._answer_written()
        r = self.client.get(reverse("placement_result", args=[self.attempt.id]))
        self.assertRedirects(r, reverse("placement_voice_handoff", args=[self.attempt.id]),
                             fetch_redirect_response=False)
        self.assertFalse(PlacementResult.objects.filter(user=self.user).exists())
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.placement_completed)

    # ---- 2: too-short speaking → blocked + retryable ----
    def test_too_short_speaking_blocks_and_is_retryable(self):
        self._answer_written()
        r = self._voice(2, with_eval=True)
        self.assertEqual(r.status_code, 302)
        self.assertIn("voice-call", r.url)
        self.assertFalse(PlacementResult.objects.filter(user=self.user).exists())
        self.attempt.refresh_from_db()
        self.assertNotEqual(self.attempt.status, "completed")
        row = PlacementSpeakingAttempt.objects.filter(student=self.user).latest("started_at")
        self.assertEqual(row.status, "needs_retry")
        self.assertFalse(row.is_used_attempt)
        self.assertFalse(speaking_quota.has_used_attempt(self.user))  # can retry

    # ---- 3: STT / VoiceCallEvaluation failure → no crash, no result, retry ----
    def test_stt_failure_no_crash_no_result(self):
        self._answer_written()
        r = self._voice(5, with_eval=False)   # answers present but eval missing
        self.assertEqual(r.status_code, 302)   # no crash
        self.assertFalse(PlacementResult.objects.filter(user=self.user).exists())
        self.attempt.refresh_from_db()
        self.assertNotEqual(self.attempt.status, "completed")
        self.assertFalse(speaking_quota.has_used_attempt(self.user))
        # No AI-Tutor minutes burned by the gate.
        self.assertFalse(UserDailyQuota.objects.filter(
            user=self.user, ai_tutor_seconds_used__gt=0).exists())

    # ---- 4: valid speaking → finalises + course assigned ----
    def test_valid_speaking_finalises_and_assigns(self):
        self._answer_written()
        r = self._voice(5, with_eval=True)
        self.assertRedirects(r, reverse("placement_result", args=[self.attempt.id]),
                             fetch_redirect_response=False)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "completed")
        self.assertTrue(PlacementResult.objects.filter(user=self.user).exists())
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.placement_completed)
        # And the result page now renders.
        self.assertEqual(self.client.get(
            reverse("placement_result", args=[self.attempt.id])).status_code, 200)

    # ---- 5: course assignment only after written+speaking ----
    def test_course_not_assigned_until_speaking_complete(self):
        self._answer_written()
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.placement_completed)  # written alone → no
        self._voice(5, with_eval=True)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.placement_completed)   # after speaking → yes

    # ---- 6: gate never consumes AI-Tutor minutes ----
    def test_gate_does_not_consume_minutes(self):
        self._answer_written()
        self._voice(1, with_eval=True)   # too short → blocked
        self.assertFalse(UserDailyQuota.objects.filter(
            user=self.user, ai_tutor_seconds_used__gt=0).exists())

    # ---- 8: tutor asked all questions, student couldn't → conservative finalise ----
    def test_unable_after_full_call_finalises_conservatively(self):
        self._answer_written()
        # Tutor asked all 5 questions; student managed only 1 answer.
        r = self._voice(1, with_eval=True, tutor_questions=5)
        self.assertRedirects(r, reverse("placement_result", args=[self.attempt.id]),
                             fetch_redirect_response=False)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "completed")          # not blocked forever
        self.assertIn(self.attempt.recommended_cefr_level, {"A0", "A1"})  # conservative cap
        result = PlacementResult.objects.filter(user=self.user).latest("created_at")
        self.assertEqual(result.transcript.get("speaking_status"),
                         "unable_to_answer_after_retries")
        self.assertEqual(result.speaking_score, 0)
        row = PlacementSpeakingAttempt.objects.filter(student=self.user).latest("started_at")
        self.assertEqual(row.status, "unable_to_answer_after_retries")
        self.assertTrue(row.is_used_attempt)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.placement_completed)

    # ---- 9: repeated short calls reach unable after max retries ----
    @override_settings(PLACEMENT_SPEAKING_MAX_RETRIES=3)
    def test_repeated_silence_reaches_unable_after_max_retries(self):
        self._answer_written()
        # Two short calls where the tutor only got through 1 question → retry.
        self.assertEqual(self._voice(1, with_eval=True, tutor_questions=1).status_code, 302)
        self.assertFalse(PlacementResult.objects.filter(user=self.user).exists())
        self.assertEqual(self._voice(1, with_eval=True, tutor_questions=1).status_code, 302)
        self.assertFalse(PlacementResult.objects.filter(user=self.user).exists())
        # Third failed attempt exhausts retries → conservative finalise.
        self._voice(1, with_eval=True, tutor_questions=1)
        self.assertTrue(PlacementResult.objects.filter(user=self.user).exists())
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "completed")

    # ---- 10: tutor-led helper text is shown on the call page ----
    def test_call_page_shows_tutor_led_helper(self):
        self._answer_written()
        conv = self.attempt.voice_conversation
        resp = self.client.get(
            f"/tutor/{conv.pk}/voice-call/?placement_attempt={self.attempt.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("استمع إلى السؤال", resp.content.decode())

    # ---- 7: admin override finalises explicitly ----
    def test_admin_override_finalises(self):
        self._answer_written()
        admin = User.objects.create_user("adm@x.com", "adm@x.com", "pw", is_staff=True)
        with self.assertRaises(admin_override.OverrideError):
            admin_override.admin_finalise_placement(
                student=self.user, actor=admin, reason="  ", level="B1")
        attempt, result = admin_override.admin_finalise_placement(
            student=self.user, actor=admin, reason="Verified offline interview", level="B1")
        self.assertEqual(result.level, "B1")
        self.assertEqual(attempt.status, "completed")
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.placement_completed)
        self.assertEqual(self.user.profile.cefr_level, "B1")
        # Audit recorded.
        self.assertEqual(result.transcript.get("source"), "admin_override")
        self.assertEqual(result.transcript.get("reason"), "Verified offline interview")
