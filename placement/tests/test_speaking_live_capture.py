"""Live per-question answer capture + per-question hybrid coverage.

The reliable binding is live: the browser saves each FINAL student transcript
with its explicit question_id while the call runs. Finalise then trusts those
per question and only backfills the MISSING ones from the fallback — it never
re-distributes the whole conversation over correctly-bound answers.
"""
from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from placement.models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementQuestion,
)
from placement.services import speaking_alignment as sa
from placement.services.placement_question_selector import create_placement_attempt
from tutor.models import TutorConversation, TutorMessage

User = get_user_model()

NO_AI = patch("ai_usage.services.ai_client.complete_text", side_effect=RuntimeError("no-ai"))


@override_settings(AXES_ENABLED=False)
class LiveAnswerEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user("lc@x.com", "lc@x.com", "pw")
        self.client.force_login(self.user)
        self.attempt = create_placement_attempt(self.user)
        self.sk = {  # question_text → PlacementAttemptQuestion
            r.question.question_text: r
            for r in self.attempt.questions.filter(section="speaking").select_related("question")
        }
        self.url = reverse("placement_speaking_answer", args=[self.attempt.id])

    def _post(self, **payload):
        return self.client.post(self.url, data=json.dumps(payload),
                                content_type="application/json")

    def _q(self, text):
        return self.sk[text].id

    def test_requires_question_id(self):
        r = self._post(transcript="My name is Sam")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "missing_question_id")

    def test_rejects_empty(self):
        r = self._post(question_id=self._q("What is your name?"), transcript="   ")
        self.assertEqual(r.status_code, 400)

    def test_rejects_tutor_pleasantry(self):
        qid = self._q("What is your name?")
        for txt in ("Great", "Right?", "Okay", "Thank you"):
            r = self._post(question_id=qid, transcript=txt)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json().get("skipped"), "pleasantry")
        self.sk["What is your name?"].refresh_from_db()
        self.assertEqual(self.sk["What is your name?"].transcript, "")

    def test_saves_answer_to_the_explicit_question(self):
        self._post(question_id=self._q("How old are you?"), transcript="I am 40 years old")
        self.sk["How old are you?"].refresh_from_db()
        self.assertEqual(self.sk["How old are you?"].transcript, "I am 40 years old")
        # Other questions are untouched.
        self.sk["Where are you from?"].refresh_from_db()
        self.assertEqual(self.sk["Where are you from?"].transcript, "")

    def test_upsert_is_idempotent(self):
        qid = self._q("Where are you from?")
        self._post(question_id=qid, transcript="I come from Sudan")
        r = self._post(question_id=qid, transcript="I come from Sudan")  # retry
        self.assertTrue(r.json().get("dedup"))
        self.sk["Where are you from?"].refresh_from_db()
        self.assertEqual(self.sk["Where are you from?"].transcript, "I come from Sudan")

    def test_extracts_relevant_clause_not_the_whole_ramble(self):
        # A country answer that also blurts the job → keep only the country part.
        self._post(question_id=self._q("Where are you from?"),
                   transcript="I come from Sudan. I am a teacher and administrative assistant.")
        self.sk["Where are you from?"].refresh_from_db()
        saved = self.sk["Where are you from?"].transcript
        self.assertIn("Sudan", saved)
        self.assertNotIn("teacher", saved.lower())

    def test_cannot_save_to_another_users_attempt(self):
        other = User.objects.create_user("o@x.com", "o@x.com", "pw")
        oa = create_placement_attempt(other)
        oq = oa.questions.filter(section="speaking").first()
        r = self._post(question_id=oq.id, transcript="hi")  # qid not in MY attempt
        self.assertEqual(r.status_code, 404)


@override_settings(AXES_ENABLED=False)
class HybridCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def setUp(self):
        self.user = User.objects.create_user("hc@x.com", "hc@x.com", "pw")
        self.attempt = create_placement_attempt(self.user)
        self.conv = TutorConversation.objects.create(user=self.user, topic="placement")
        self.attempt.voice_conversation = self.conv
        self.attempt.save(update_fields=["voice_conversation"])
        self.rows = {
            r.question.question_text: r
            for r in self.attempt.questions.filter(section="speaking").select_related("question")
        }

    def _save_live(self, text, transcript):
        r = self.rows[text]
        r.transcript = transcript
        r.save(update_fields=["transcript"])

    def _turns(self, script):
        for role, content in script:
            TutorMessage.objects.create(conversation=self.conv, role=role, content=content)

    def test_full_live_only_rescores_and_keeps_mapping(self):
        live = {
            "What is your name?": "My name is Hasawo",
            "How old are you?": "I am 40 years old",
            "Where are you from?": "I come from Sudan",
            "What do you do for a living?": "I am a teacher and administrative assistant",
            "Why do you want to learn English?": "To improve my English",
        }
        for text, ans in live.items():
            self._save_live(text, ans)
        # A misleading conversation transcript exists too — must be ignored.
        self._turns([("assistant", "Where are you from?"), ("user", "I am 40 years old")])
        from placement.views import map_speaking_transcript
        with NO_AI:
            map_speaking_transcript(self.attempt, self.conv, None)
        for text, ans in live.items():
            self.rows[text].refresh_from_db()
            self.assertEqual(self.rows[text].transcript, ans)   # mapping unchanged
            self.assertIsNotNone(self.rows[text].score)         # only (re)scored

    def test_partial_live_keeps_correct_and_backfills_missing(self):
        # Only Q1 captured live; the conversation has a WRONG Q1 answer that
        # must NOT overwrite the live one, plus real Q2-Q5 to backfill.
        self._save_live("What is your name?", "My name is LIVE")
        self._turns([
            ("assistant", "What is your name?"), ("user", "this is a wrong name turn"),
            ("assistant", "How old are you?"), ("user", "I am 40 years old"),
            ("assistant", "Where are you from?"), ("user", "I come from Sudan"),
            ("assistant", "What do you do for a living?"), ("user", "I am a teacher"),
            ("assistant", "Why do you want to learn English?"), ("user", "To improve my English"),
        ])
        from placement.views import map_speaking_transcript
        with NO_AI:
            map_speaking_transcript(self.attempt, self.conv, None)
        self.rows["What is your name?"].refresh_from_db()
        self.assertEqual(self.rows["What is your name?"].transcript, "My name is LIVE")  # live kept
        self.rows["How old are you?"].refresh_from_db()
        self.assertEqual(self.rows["How old are you?"].transcript, "I am 40 years old")  # backfilled
        self.rows["Where are you from?"].refresh_from_db()
        self.assertEqual(self.rows["Where are you from?"].transcript, "I come from Sudan")

    def test_live_q3_not_replaced_by_long_fallback(self):
        self._save_live("Where are you from?", "I come from Sudan")
        # A long mixed reconstruction must never overwrite the live Q3.
        self._turns([
            ("assistant", "Why do you want to learn English?"),
            ("user", "My name is X. I am 40 years old. I am a teacher. I want to learn "
                     "English because I need it for work."),
        ])
        from placement.views import map_speaking_transcript
        with NO_AI:
            map_speaking_transcript(self.attempt, self.conv, None)
        self.rows["Where are you from?"].refresh_from_db()
        self.assertEqual(self.rows["Where are you from?"].transcript, "I come from Sudan")


class ExtractClauseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_placement_questions", stdout=StringIO())

    def test_extract_country_and_job_from_mixed(self):
        country = PlacementQuestion.objects.get(code="sp.v2.003")
        job = PlacementQuestion.objects.get(code="sp.v2.004")
        mixed = "I come from Sudan. I am a teacher and administrative assistant."
        self.assertIn("Sudan", sa.extract_relevant_answer_for_question(country, mixed))
        self.assertNotIn("teacher", sa.extract_relevant_answer_for_question(country, mixed).lower())
        self.assertIn("teacher", sa.extract_relevant_answer_for_question(job, mixed).lower())
        self.assertNotIn("sudan", sa.extract_relevant_answer_for_question(job, mixed).lower())

    def test_q5_does_not_swallow_the_whole_chat(self):
        reason = PlacementQuestion.objects.get(code="sp.v2.005")
        whole = ("My name is Hasawo. I am 40 years old. I am Sudanese. I am a teacher. "
                 "I want to learn English because I need it for my job.")
        out = sa.extract_relevant_answer_for_question(reason, whole)
        self.assertIn("learn English", out)
        self.assertNotIn("My name is Hasawo", out)
        self.assertNotIn("40 years old", out)
