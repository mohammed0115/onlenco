"""Tests for the SPA chat endpoint at /api/v1/tutor/chat/send/.

Replaces the form-POST flow with a JSON-only AJAX path; these tests pin
the contract so the front-end doesn't break silently when someone
re-introduces a redirect or HTML response.
"""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tutor.models import TutorConversation, TutorMessage

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class ChatSendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="spa@x.com", email="spa@x.com", password="pw",
        )
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.conv = TutorConversation.objects.create(user=self.user)
        self.client.login(username="spa@x.com", password="pw")
        self.url = reverse("api_tutor_chat_send")

    def test_anonymous_returns_401_json(self):
        self.client.logout()
        r = self.client.post(self.url, {"message": "hi"}, content_type="application/json")
        self.assertIn(r.status_code, (401, 403))   # IsAuthenticated → 401/403, never 302
        self.assertEqual(r["Content-Type"].split(";")[0], "application/json")

    def test_returns_json_not_html(self):
        with patch("tutor.api.views.chat", return_value="Hi back."):
            r = self.client.post(
                self.url,
                {"message": "hello", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"].split(";")[0], "application/json")
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["user_message"]["content"], "hello")
        self.assertIn("Hi back", body["ai_message"]["content"])
        # speech_text exists for browser TTS
        self.assertIn("speech_text", body["ai_message"])

    def test_persists_both_messages(self):
        with patch("tutor.api.views.chat", return_value="reply"):
            self.client.post(
                self.url,
                {"message": "hi", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(self.conv.messages.count(), 2)
        self.assertEqual(self.conv.messages.first().role, "user")
        self.assertEqual(self.conv.messages.last().role, "assistant")

    def test_creates_conversation_when_id_omitted(self):
        with patch("tutor.api.views.chat", return_value="reply"):
            r = self.client.post(
                self.url, {"message": "hi"}, content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        new_id = r.json()["conversation_id"]
        self.assertNotEqual(new_id, self.conv.id)
        self.assertTrue(TutorConversation.objects.filter(id=new_id).exists())

    def test_blocks_other_users_conversation(self):
        other = User.objects.create_user(username="other@x.com", password="pw")
        other_conv = TutorConversation.objects.create(user=other)
        r = self.client.post(
            self.url,
            {"message": "hi", "conversation_id": other_conv.id},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)
        body = r.json()
        self.assertFalse(body["success"])

    def test_empty_message_returns_400_not_redirect(self):
        r = self.client.post(
            self.url, {"message": "  "}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "empty_message")

    def test_unsubscribed_user_gets_402(self):
        self.user.profile.subscription_status = "inactive"
        self.user.profile.save()
        r = self.client.post(
            self.url, {"message": "hi"}, content_type="application/json",
        )
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()["error"], "subscription_required")

    def test_voice_flag_propagates_to_chat_service(self):
        with patch("tutor.api.views.chat", return_value="ok") as mock_chat:
            self.client.post(
                self.url,
                {"message": "hi", "conversation_id": self.conv.id, "voice": True},
                content_type="application/json",
            )
        _, kwargs = mock_chat.call_args
        self.assertTrue(kwargs.get("voice"))


@override_settings(AXES_ENABLED=False)
class ChatHistoryRenderTests(TestCase):
    """The detail page still renders the existing transcript server-side
    so the first paint isn't blank. The SPA appends new messages on top
    of that initial DOM."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="hist@x.com", password="pw",
        )
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.client.login(username="hist@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user, title="t")
        TutorMessage.objects.create(conversation=self.conv, role="user", content="prev hello")
        TutorMessage.objects.create(conversation=self.conv, role="assistant", content="prev reply")

    def test_detail_page_renders_existing_messages(self):
        r = self.client.get(reverse("tutor_detail", args=[self.conv.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("prev hello", body)
        self.assertIn("prev reply", body)
        # And the SPA bootstrap is wired
        self.assertIn("onlencoTutor", body)
        self.assertIn("/api/v1/tutor/chat/send/", body)
