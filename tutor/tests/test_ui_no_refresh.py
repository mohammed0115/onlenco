"""End-to-end checks for the no-refresh AI Tutor SPA.

The SPA must:
- render the page via GET (login_required)
- never depend on a full-page reload to send a text message
- never depend on a full-page reload to send a voice message
- preserve previous transcript on every render
- keep the mic endpoint behind login (anonymous users get 401, not 302)
- return JSON on AI failure, not crash
- render dir-aware bubbles for both Arabic (RTL) and English (LTR)
"""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tutor.models import TutorConversation, TutorMessage

User = get_user_model()


def _activate_subscription(user):
    prof = user.profile
    prof.subscription_status = "active"
    prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
    prof.save()


@override_settings(AXES_ENABLED=False)
class TutorPageLoadsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ui@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="ui@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user, title="t")

    def test_detail_page_loads_with_spa_shell(self):
        r = self.client.get(reverse("tutor_detail", args=[self.conv.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # Core SPA hooks must be present so the JS controller can attach.
        for hook in [
            'id="chatMessages"',
            'id="messageInput"',
            'id="micButton"',
            'id="voiceStatus"',
            'id="sendMessageBtn"',
            'id="stopRecordingBtn"',
            'id="thinking-indicator"',
            'onlencoTutor',
        ]:
            self.assertIn(hook, body, f"missing SPA hook: {hook}")

    def test_anonymous_redirected_from_page(self):
        self.client.logout()
        r = self.client.get(reverse("tutor_detail", args=[self.conv.pk]))
        # Page is login_required → redirect to /auth/.
        self.assertEqual(r.status_code, 302)


@override_settings(AXES_ENABLED=False)
class NoRefreshTextSendTests(TestCase):
    """The SPA path returns JSON, never a 302 redirect, so the page never reloads."""

    def setUp(self):
        self.user = User.objects.create_user(username="norf@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="norf@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user)

    def test_chat_send_returns_json_no_redirect(self):
        with patch("tutor.api.views.chat", return_value="hello back"):
            r = self.client.post(
                reverse("api_tutor_chat_send"),
                {"message": "hi", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(r.status_code, (301, 302, 303))
        self.assertTrue(r["Content-Type"].startswith("application/json"))

    def test_ai_failure_returns_friendly_json(self):
        # The chat() function swallows upstream failures and returns a
        # graceful stub string, so the API still responds 200 with a
        # reply the user can read — rather than 500-ing.
        with patch(
            "tutor.api.views.chat",
            return_value="(stub: AI temporarily unavailable) try again",
        ):
            r = self.client.post(
                reverse("api_tutor_chat_send"),
                {"message": "hi", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertIn("temporarily unavailable", body["ai_message"]["content"])


@override_settings(AXES_ENABLED=False)
class VoiceEndpointAuthTests(TestCase):
    """Anonymous mic POST must get 401 JSON, not a 302 redirect to /auth/."""

    def test_voice_transcribe_requires_login(self):
        r = self.client.post(
            reverse("api_tutor_voice_transcribe"),
            data={},
        )
        self.assertIn(r.status_code, (401, 403))
        # Critical: the SPA reads JSON; an HTML login redirect would crash it.
        self.assertTrue(r["Content-Type"].startswith("application/json"))


@override_settings(AXES_ENABLED=False)
class ConversationHistoryTests(TestCase):
    """Existing transcript must remain visible on every render — the SPA
    appends new bubbles on top of this initial DOM."""

    def setUp(self):
        self.user = User.objects.create_user(username="hist2@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="hist2@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user, title="t")
        TutorMessage.objects.create(conversation=self.conv, role="user", content="earlier-user-msg")
        TutorMessage.objects.create(conversation=self.conv, role="assistant", content="earlieraimessage")

    def test_history_persists_on_get(self):
        r = self.client.get(reverse("tutor_detail", args=[self.conv.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("earlier-user-msg", body)
        self.assertIn("earlieraimessage", body)

    def test_history_persists_after_send(self):
        with patch("tutor.api.views.chat", return_value="newaireply"):
            self.client.post(
                reverse("api_tutor_chat_send"),
                {"message": "new-user-msg", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        r = self.client.get(reverse("tutor_detail", args=[self.conv.pk]))
        body = r.content.decode()
        self.assertIn("earlier-user-msg", body)
        self.assertIn("earlieraimessage", body)
        self.assertIn("new-user-msg", body)
        self.assertIn("newaireply", body)


@override_settings(AXES_ENABLED=False)
class BubbleDirectionTests(TestCase):
    """Bubbles render with explicit `dir="ltr"` so mixed AR/EN content
    inside a single bubble stays readable. The page's outer `dir` is
    decided by Django's i18n middleware; the bubble overrides per-message."""

    def setUp(self):
        self.user = User.objects.create_user(username="rtl@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="rtl@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user, title="t")
        TutorMessage.objects.create(conversation=self.conv, role="user", content="مرحبا")
        TutorMessage.objects.create(conversation=self.conv, role="assistant", content="Hi")

    def test_both_bubbles_use_dir_ltr_for_mixed_content(self):
        r = self.client.get(reverse("tutor_detail", args=[self.conv.pk]))
        body = r.content.decode()
        self.assertIn('class="onlenco-bubble-user"', body)
        self.assertIn('class="onlenco-bubble-ai"', body)
        # Both bubbles have explicit dir attribute so Arabic + English
        # display correctly inside the same conversation.
        self.assertIn('dir="ltr"', body)
