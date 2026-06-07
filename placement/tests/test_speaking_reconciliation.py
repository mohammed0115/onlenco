"""Post-call AI reconciliation for placement SPEAKING answers.

Reconciliation re-aligns + cleans the captured answers BEFORE scoring: it
ignores noise / tutor / filler, splits a turn that holds two answers, stops Q5
swallowing the whole chat, and corrects a wrongly-bound live answer — without
ever scoring or assigning a level. It falls back to the live answers safely
when the AI is unavailable, and never consumes paid AI-Tutor minutes.
"""
from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from placement.services import speaking_alignment as sa
from placement.services import speaking_reconciliation as recon
from placement.services.placement_question_selector import create_placement_attempt
from tutor.models import TutorConversation, VoiceCallEvaluation

User = get_user_model()
NO_AI = patch("ai_usage.services.ai_client.complete_text", side_effect=RuntimeError("no-ai"))


def _rows(attempt):
    return list(
        attempt.questions.filter(section="speaking")
        .select_related("question").order_by("order")
    )


class ReconcileServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user("rc@x.com", "rc@x.com", "pw")
        self.attempt = create_placement_attempt(self.user)
        self.rows = _rows(self.attempt)
        self.by_key = {sa.question_key(r.question): r for r in self.rows}

    # -- helpers ----------------------------------------------------------

    def _ai_returns(self, mapping):
        """A complete_text mock yielding a reconciliation JSON built from
        ``{key: (clean_answer, ignored_noise, needs_review)}``."""
        answers = []
        for r in self.rows:
            key = sa.question_key(r.question)
            clean, noise, nr = mapping.get(key, ("", [], True))
            answers.append({
                "question_id": r.id, "question_order": r.order, "question_key": key,
                "clean_answer": clean, "confidence": 0.95 if clean else 0.1,
                "source": "transcript", "ignored_noise": noise, "needs_review": nr,
            })
        payload = json.dumps({"answers": answers, "global_warnings": []})
        return patch("ai_usage.services.ai_client.complete_text", return_value=payload)

    def _result_by_key(self, result):
        out = {}
        for e in result["answers"]:
            out[e["question_key"]] = e
        return out

    # -- tests ------------------------------------------------------------

    def test_noise_before_name_is_ignored_and_real_answer_used(self):
        turns = [
            {"role": "assistant", "content": "What is your name?"},
            {"role": "user", "content": "I'm not going to finish that one, I'm just going to..."},
            {"role": "user", "content": "My name is Hazawu."},
        ]
        live = ["I'm not going to finish that one, I'm just going to... My name is Hazawu",
                "", "", "", ""]
        with self._ai_returns({
            "name": ("My name is Hazawu",
                     ["I'm not going to finish that one, I'm just going to..."], False),
        }):
            result = recon.reconcile_speaking_answers(self.attempt, turns, live)
        by_key = self._result_by_key(result)
        self.assertEqual(by_key["name"]["clean_answer"], "My name is Hazawu")
        self.assertIn("I'm not going to finish that one, I'm just going to...",
                      by_key["name"]["ignored_noise"])

    def test_combined_country_job_answer_is_split(self):
        turns = [
            {"role": "assistant", "content": "Where are you from?"},
            {"role": "user", "content": "I come from Sudan. I am a teacher."},
        ]
        live = ["", "", "I come from Sudan. I am a teacher.", "", ""]
        with self._ai_returns({
            "country": ("I come from Sudan", [], False),
            "job": ("I am a teacher", [], False),
        }):
            result = recon.reconcile_speaking_answers(self.attempt, turns, live)
        by_key = self._result_by_key(result)
        self.assertEqual(by_key["country"]["clean_answer"], "I come from Sudan")
        self.assertEqual(by_key["job"]["clean_answer"], "I am a teacher")

    def test_q5_does_not_swallow_whole_conversation(self):
        long_reason = ("I want to improve myself. I need it for my job. "
                       "I also travel a lot. And for study. My future career.")
        turns = [
            {"role": "assistant", "content": "Why do you want to learn English?"},
            {"role": "user", "content": long_reason},
        ]
        live = ["", "", "", "", long_reason]
        with self._ai_returns({"reason": (long_reason, [], False)}):
            result = recon.reconcile_speaking_answers(self.attempt, turns, live)
        reason = self._result_by_key(result)["reason"]["clean_answer"]
        self.assertLessEqual(len(reason), recon.MAX_CLEAN_CHARS)
        self.assertNotIn("travel", reason)        # 3rd+ sentences dropped
        self.assertNotIn("future", reason)

    def test_tutor_words_are_never_used_as_an_answer(self):
        turns = [
            {"role": "assistant", "content": "What do you do for a living?"},
            {"role": "user", "content": "I am a teacher."},
        ]
        live = ["", "", "", "I am a teacher.", ""]
        # The AI wrongly echoes the tutor's question as the job answer.
        with self._ai_returns({"job": ("What do you do for a living", [], False)}):
            result = recon.reconcile_speaking_answers(self.attempt, turns, live)
        job = self._result_by_key(result)["job"]
        self.assertEqual(job["clean_answer"], "")     # tutor text rejected
        self.assertTrue(job["needs_review"])

    def test_live_wrong_mapping_is_corrected(self):
        turns = [
            {"role": "assistant", "content": "Where are you from?"},
            {"role": "user", "content": "I come from Sudan. I am a teacher."},
        ]
        # Live capture wrongly bound the job answer to country.
        live = ["", "", "I am a teacher", "I am a teacher", ""]
        with self._ai_returns({
            "country": ("I come from Sudan", [], False),
            "job": ("I am a teacher", [], False),
        }):
            result = recon.reconcile_speaking_answers(self.attempt, turns, live)
        by_key = self._result_by_key(result)
        self.assertEqual(by_key["country"]["clean_answer"], "I come from Sudan")

    def test_invented_answer_is_rejected(self):
        # The AI returns something the student never said → anti-invention guard.
        turns = [{"role": "user", "content": "My name is Sam."}]
        live = ["My name is Sam", "", "", "", ""]
        with self._ai_returns({"age": ("I am ninety nine years old", [], False)}):
            result = recon.reconcile_speaking_answers(self.attempt, turns, live)
        age = self._result_by_key(result)["age"]
        self.assertTrue(age["needs_review"])
        self.assertNotIn("ninety nine", age["clean_answer"])

    def test_ai_failure_falls_back_safely(self):
        turns = [
            {"role": "assistant", "content": "What is your name?"},
            {"role": "user", "content": "My name is Hazawu."},
        ]
        live = ["My name is Hazawu", "I am 40 years old", "", "", ""]
        with NO_AI:
            result = recon.reconcile_speaking_answers(self.attempt, turns, live)
        self.assertIn("reconciliation_failed", result["global_warnings"])
        by_key = self._result_by_key(result)
        # Falls back to the live answers (cleaned), never crashes.
        self.assertEqual(by_key["name"]["clean_answer"], "My name is Hazawu")
        self.assertEqual(by_key["age"]["clean_answer"], "I am 40 years old")

    @override_settings(PLACEMENT_USE_AI_RECONCILIATION=False)
    def test_disabled_uses_fallback_without_calling_ai(self):
        turns = [{"role": "user", "content": "My name is Sara."}]
        live = ["My name is Sara", "", "", "", ""]
        with patch("ai_usage.services.ai_client.complete_text") as mock_ai:
            result = recon.reconcile_speaking_answers(self.attempt, turns, live)
        mock_ai.assert_not_called()
        self.assertEqual(self._result_by_key(result)["name"]["clean_answer"], "My name is Sara")

    def test_does_not_consume_paid_ai_tutor_minutes(self):
        from ai_usage import constants as C
        # The reconciliation feature is NOT minute-bearing.
        self.assertNotIn(C.FEATURE_PLACEMENT_RECONCILE,
                         C.MINUTE_BEARING_FEATURES)
        turns = [{"role": "user", "content": "My name is Sara."}]
        live = ["My name is Sara", "", "", "", ""]
        with self._ai_returns({"name": ("My name is Sara", [], False)}) as mock_ai:
            recon.reconcile_speaking_answers(self.attempt, turns, live)
        # And the call explicitly disables minute enforcement.
        self.assertTrue(mock_ai.called)
        kwargs = mock_ai.call_args.kwargs
        self.assertEqual(kwargs.get("feature"), C.FEATURE_PLACEMENT_RECONCILE)
        self.assertFalse(kwargs.get("enforce_minutes", True))


@override_settings(AXES_ENABLED=False)
class ReconcileIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user("ri@x.com", "ri@x.com", "pw")
        self.attempt = create_placement_attempt(self.user)
        self.conv = TutorConversation.objects.create(user=self.user, topic="placement")
        self.attempt.voice_conversation = self.conv
        self.attempt.save(update_fields=["voice_conversation"])
        self.rows = _rows(self.attempt)

    def _ai_clean(self, mapping):
        answers = []
        for r in self.rows:
            key = sa.question_key(r.question)
            clean = mapping.get(key, "")
            answers.append({
                "question_id": r.id, "question_order": r.order, "question_key": key,
                "clean_answer": clean, "confidence": 0.95 if clean else 0.1,
                "source": "transcript", "ignored_noise": [], "needs_review": not clean,
            })
        return json.dumps({"answers": answers, "global_warnings": []})

    def test_clean_answers_are_used_for_scoring_and_raw_is_preserved(self):
        from placement.views import map_speaking_transcript
        # Live capture stored a noisy answer on the name row.
        live_map = {
            "name": "uh, I'm not going to finish... My name is Hazawu",
            "age": "I am 40 years old",
            "country": "I am from Sudan",
            "job": "I am a teacher",
            "reason": "Because I need it for my job",
        }
        for r in self.rows:
            r.transcript = live_map[sa.question_key(r.question)]
            r.save(update_fields=["transcript"])
        clean_map = {
            "name": "My name is Hazawu", "age": "I am 40 years old",
            "country": "I am from Sudan", "job": "I am a teacher",
            "reason": "Because I need it for my job",
        }
        # complete_text returns the reconciliation JSON for ALL calls; the
        # scorer can't parse that shape and gracefully heuristics the CLEAN
        # answers — exactly the path we want to assert.
        with patch("ai_usage.services.ai_client.complete_text",
                   return_value=self._ai_clean(clean_map)):
            map_speaking_transcript(self.attempt, self.conv, None)
        name_row = next(r for r in _rows(self.attempt)
                        if sa.question_key(r.question) == "name")
        self.assertEqual(name_row.transcript, "My name is Hazawu")     # CLEAN used
        self.assertGreater(name_row.score, 0)                          # scored
        self.assertIn("not going to finish", name_row.error_analysis["raw_answer"])  # raw kept

    def test_score_based_cefr_still_maps_96_to_c2(self):
        from placement.services.level_mapping import level_for_percentage
        self.assertEqual(level_for_percentage(96), "C2")
        self.assertEqual(level_for_percentage(60), "A2")
