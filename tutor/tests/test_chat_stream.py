"""Tests for the typewriter SSE endpoint at /api/v1/tutor/chat/stream/."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tutor.models import TutorConversation, TutorMessage

User = get_user_model()


def _consume_sse(response) -> list:
    """Read the full streaming body and return a list of parsed events."""
    body = b"".join(response.streaming_content).decode("utf-8")
    events = []
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


@override_settings(AXES_ENABLED=False, AI_API_KEY="")
class ChatStreamTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="s@x.com", email="s@x.com", password="pw",
        )
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.conv = TutorConversation.objects.create(user=self.user)
        self.client.login(username="s@x.com", password="pw")
        self.url = reverse("api_tutor_chat_stream")

    def test_anonymous_returns_401_json(self):
        self.client.logout()
        r = self.client.post(
            self.url, json.dumps({"message": "hi"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r["Content-Type"].split(";")[0], "application/json")

    def test_emits_start_token_and_done(self):
        # AI_API_KEY="" routes through the deterministic stub generator
        # so the SSE shape is exercised without a real network call.
        r = self.client.post(
            self.url,
            json.dumps({"message": "hi", "conversation_id": self.conv.id}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/event-stream")
        events = _consume_sse(r)
        types = [e["type"] for e in events]
        self.assertEqual(types[0], "start")
        self.assertEqual(types[-1], "done")
        # Token events reconstruct the full reply.
        tokens = "".join(e.get("token", "") for e in events if e["type"] == "token")
        self.assertEqual(tokens, events[-1]["content"])
        # Final event includes humanised + speech-clean copy.
        done = events[-1]
        self.assertIn("content_humanized", done)
        self.assertIn("speech_text", done)

    def test_persists_user_and_ai_messages(self):
        r = self.client.post(
            self.url,
            json.dumps({"message": "hello", "conversation_id": self.conv.id}),
            content_type="application/json",
        )
        list(r.streaming_content)  # drain to fire the persist step
        msgs = list(self.conv.messages.order_by("created_at"))
        self.assertEqual([m.role for m in msgs], ["user", "assistant"])
        self.assertEqual(msgs[0].content, "hello")
        # Assistant content is non-empty (real text was streamed + persisted)
        self.assertTrue(msgs[1].content)
        self.assertIn("hello", msgs[1].content)   # stub echoes user text

    def test_blocks_other_users_conversation(self):
        other = User.objects.create_user(username="o@x.com", password="pw")
        other_conv = TutorConversation.objects.create(user=other)
        r = self.client.post(
            self.url,
            json.dumps({"message": "hi", "conversation_id": other_conv.id}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)

    def test_empty_message_returns_400(self):
        r = self.client.post(
            self.url,
            json.dumps({"message": "  ", "conversation_id": self.conv.id}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "empty_message")

    def test_unsubscribed_user_gets_402(self):
        self.user.profile.subscription_status = "inactive"
        self.user.profile.save()
        r = self.client.post(
            self.url, json.dumps({"message": "hi"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 402)

    def test_creates_conversation_when_id_omitted(self):
        r = self.client.post(
            self.url, json.dumps({"message": "hi"}),
            content_type="application/json",
        )
        list(r.streaming_content)
        # Each call without a conversation_id creates a new row.
        new_id = TutorConversation.objects.filter(user=self.user).exclude(id=self.conv.id).first().id
        self.assertIsNotNone(new_id)
