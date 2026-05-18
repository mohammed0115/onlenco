"""Sprint 4 tests: text normalization, library audio session lifecycle, quota."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.services.reading_prep import (
    TTS_CHUNK_LIMIT_CHARS,
    DOTTED_ABBREVIATIONS,
    EXPANSIONS,
    prepare_for_reading,
)
from subscriptions.models import (
    LibraryAudioSession,
    SubscriptionPlan,
    TextNormalizationLog,
    UserDailyQuota,
)
from subscriptions.services import library_audio_service, subscription_service


User = get_user_model()


# ---------------------------------------------------------------------------
# Pure normalization tests (no DB / HTTP)
# ---------------------------------------------------------------------------

class NormalizationRulesTests(TestCase):
    def test_underscores_between_words_are_stripped(self):
        out = prepare_for_reading("Chapter_1: The_Beginning")["tts_ready_text"]
        # Result no longer contains a literal underscore between letters.
        self.assertNotRegex(out, r"\w_\w")

    def test_markdown_bold_stripped(self):
        out = prepare_for_reading("This is **important** information.")["tts_ready_text"]
        self.assertIn("important", out)
        self.assertNotIn("**", out)

    def test_uae_becomes_dotted_spelling(self):
        out = prepare_for_reading("The UAE is a country.")["tts_ready_text"]
        self.assertIn("U.A.E.", out)
        # Boundary check: a real word containing the letters must not be touched.
        out2 = prepare_for_reading("nuance")["tts_ready_text"]
        self.assertIn("nuance", out2)

    def test_etc_expanded(self):
        out = prepare_for_reading("Apples, oranges, etc. are fruits.")["tts_ready_text"]
        self.assertIn("et cetera", out)

    def test_repeated_punctuation_collapsed(self):
        out = prepare_for_reading("Really?? Why!!! Stop......")["tts_ready_text"]
        self.assertNotIn("??", out)
        self.assertNotIn("!!", out)

    def test_literal_symbol_words_stripped(self):
        # If raw text contains "underscore underscore" as decoration, it must not be spoken.
        out = prepare_for_reading("Title underscore underscore Hello")["tts_ready_text"]
        self.assertNotIn("underscore underscore", out.lower())

    def test_orphan_asterisks_stripped(self):
        out = prepare_for_reading("This is *partial bold")["tts_ready_text"]
        self.assertNotIn("*", out)

    def test_applied_rules_listed(self):
        result = prepare_for_reading("The UAE has _strict_ rules.")
        self.assertTrue(any("dotted:UAE" in r for r in result["applied_rules"]))

    def test_no_change_for_clean_prose(self):
        clean = "Hello, my name is Ahmed. How are you?"
        result = prepare_for_reading(clean)
        self.assertEqual(result["tts_ready_text"], clean)

    def test_chunking_respects_limit(self):
        long_text = ("Hello world. " * 600).strip()
        result = prepare_for_reading(long_text)
        self.assertGreater(len(result["chunks"]), 1)
        for chunk in result["chunks"]:
            self.assertLessEqual(len(chunk), TTS_CHUNK_LIMIT_CHARS)

    def test_chunking_short_text_one_chunk(self):
        result = prepare_for_reading("Short story. Two sentences.")
        self.assertEqual(len(result["chunks"]), 1)

    def test_empty_text_yields_empty_chunks(self):
        result = prepare_for_reading("")
        self.assertEqual(result["tts_ready_text"], "")
        self.assertEqual(result["chunks"], [])

    def test_force_split_for_pathologically_long_sentence(self):
        long_sentence = "word " * (TTS_CHUNK_LIMIT_CHARS // 4 + 200)
        result = prepare_for_reading(long_sentence)
        # No chunk exceeds the limit even though the sentence is one giant blob.
        for chunk in result["chunks"]:
            self.assertLessEqual(len(chunk), TTS_CHUNK_LIMIT_CHARS)


# ---------------------------------------------------------------------------
# Service-layer tests (DB)
# ---------------------------------------------------------------------------

class LibraryAudioServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lib@example.com", email="lib@example.com", password="pw")
        # Subscribed user — 30 min/day library quota on the basic plan.
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(user=self.user, plan=plan, duration_days=30)

    def test_prepare_persists_normalization_log(self):
        library_audio_service.prepare(
            "Hello _world_ from UAE!",
            language="en",
            source="library_chapter",
            source_id=42,
        )
        log = TextNormalizationLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.source_id, 42)
        self.assertIn("U.A.E.", log.tts_ready_text)
        self.assertGreater(len(log.applied_rules), 0)

    def test_prepare_no_log_when_disabled(self):
        library_audio_service.prepare("Some text.", persist_log=False)
        self.assertFalse(TextNormalizationLog.objects.exists())

    def test_start_session_creates_in_progress_row(self):
        session = library_audio_service.start_session(
            self.user, chapter_id=7, chapter_title="Ch1",
        )
        self.assertEqual(session.status, "in_progress")
        self.assertEqual(session.chapter_id, 7)
        self.assertEqual(session.chapter_title, "Ch1")

    def test_concurrent_session_blocked(self):
        library_audio_service.start_session(self.user, chapter_id=1)
        with self.assertRaises(library_audio_service.LibraryConcurrentSessionExists):
            library_audio_service.start_session(self.user, chapter_id=2)

    def test_quota_exhausted_blocks_start(self):
        # Drain the library bucket (basic plan: 30 min = 1800s).
        from subscriptions.services.quota_service import consume_library_seconds
        consume_library_seconds(self.user, 1800)
        with self.assertRaises(library_audio_service.LibraryQuotaExhausted):
            library_audio_service.start_session(self.user, chapter_id=1)

    def test_no_subscription_no_quota(self):
        u = User.objects.create_user(username="no@example.com", email="no@example.com", password="pw")
        with self.assertRaises(library_audio_service.LibraryQuotaExhausted):
            library_audio_service.start_session(u, chapter_id=1)

    def test_end_session_deducts_quota(self):
        session = library_audio_service.start_session(self.user, chapter_id=1)
        closed = library_audio_service.end_session(session.pk, actual_seconds=120)
        self.assertEqual(closed.status, "completed")
        self.assertEqual(closed.consumed_seconds, 120)
        quota = UserDailyQuota.objects.get(user=self.user)
        self.assertEqual(quota.library_seconds_used, 120)

    def test_end_session_idempotent(self):
        session = library_audio_service.start_session(self.user, chapter_id=1)
        library_audio_service.end_session(session.pk, actual_seconds=60)
        library_audio_service.end_session(session.pk, actual_seconds=60)  # retry
        quota = UserDailyQuota.objects.get(user=self.user)
        self.assertEqual(quota.library_seconds_used, 60)  # not 120

    def test_cancel_session_does_not_deduct(self):
        session = library_audio_service.start_session(self.user, chapter_id=1)
        library_audio_service.cancel_session(session.pk)
        self.assertEqual(UserDailyQuota.objects.filter(user=self.user).first().library_seconds_used if UserDailyQuota.objects.filter(user=self.user).exists() else 0, 0)


# ---------------------------------------------------------------------------
# HTTP endpoint tests (uses real library.Chapter)
# ---------------------------------------------------------------------------

class LibraryAudioEndpointsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ep@example.com", email="ep@example.com", password="pw")
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(user=self.user, plan=plan, duration_days=30)
        self.client.force_login(self.user)

        from library.models import Book, Chapter
        self.book = Book.objects.create(
            title="Test Book", author="Tester", category="novel",
            level="A1", is_published=True,
        )
        self.chapter = Chapter.objects.create(
            book=self.book, title="Chapter 1",
            body="Hello _world_. The UAE is great. Etc.",
            sort_order=1,
        )

    def test_listen_page_renders(self):
        response = self.client.get(reverse("library_chapter_listen", args=[self.chapter.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "U.A.E.")
        self.assertContains(response, self.chapter.title)

    def test_audio_start_returns_chunks(self):
        response = self.client.post(reverse("library_audio_start", args=[self.chapter.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("audio_session_id", data)
        self.assertGreater(len(data["chunks"]), 0)

    def test_audio_start_402_when_quota_exhausted(self):
        from subscriptions.services.quota_service import consume_library_seconds
        consume_library_seconds(self.user, 5000)
        response = self.client.post(reverse("library_audio_start", args=[self.chapter.pk]))
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["error"], "limit_reached")

    def test_audio_start_409_on_concurrent(self):
        self.client.post(reverse("library_audio_start", args=[self.chapter.pk]))
        response = self.client.post(reverse("library_audio_start", args=[self.chapter.pk]))
        self.assertEqual(response.status_code, 409)

    def test_audio_finish_deducts(self):
        start = self.client.post(reverse("library_audio_start", args=[self.chapter.pk])).json()
        sid = start["audio_session_id"]
        finish = self.client.post(
            reverse("library_audio_finish", args=[self.chapter.pk]),
            data=json.dumps({"audio_session_id": sid, "seconds": 45}),
            content_type="application/json",
        )
        self.assertEqual(finish.status_code, 200)
        data = finish.json()
        self.assertEqual(data["seconds_consumed"], 45)

    def test_audio_finish_404_for_unknown_session(self):
        response = self.client.post(
            reverse("library_audio_finish", args=[self.chapter.pk]),
            data=json.dumps({"audio_session_id": 99999, "seconds": 10}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_audio_finish_403_for_other_users_session(self):
        other = User.objects.create_user(username="ot@example.com", email="ot@example.com", password="pw")
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(user=other, plan=plan, duration_days=30)
        from subscriptions.services.library_audio_service import start_session
        other_session = start_session(other, chapter_id=self.chapter.pk)
        response = self.client.post(
            reverse("library_audio_finish", args=[self.chapter.pk]),
            data=json.dumps({"audio_session_id": other_session.pk, "seconds": 10}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_audio_chunk_requires_open_session(self):
        response = self.client.post(
            reverse("library_audio_chunk", args=[self.chapter.pk]),
            data=json.dumps({"audio_session_id": 99999, "chunk": "Hi."}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_audio_chunk_calls_synthesize_for_open_session(self):
        start = self.client.post(reverse("library_audio_start", args=[self.chapter.pk])).json()
        sid = start["audio_session_id"]
        with patch(
            "subscriptions.services.library_audio_service.synthesize_chunk",
            return_value={"audio_b64": "AA==", "format": "mp3", "voice": "alloy"},
        ):
            response = self.client.post(
                reverse("library_audio_chunk", args=[self.chapter.pk]),
                data=json.dumps({"audio_session_id": sid, "chunk": "Hello."}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["audio_b64"], "AA==")
