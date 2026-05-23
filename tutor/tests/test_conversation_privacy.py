"""Privacy controls for AI Tutor conversations.

Two ways data leaves the DB:
  1. Self-service — the user clicks "Delete my AI Tutor conversations"
     on /auth/profile/, which POSTs to ``tutor_delete_my_conversations``.
  2. Automatic purge — the ``purge_old_tutor_conversations`` management
     command, run from cron, deletes conversations older than the
     retention window (default 90 days).
"""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tutor.models import TutorConversation, TutorMessage


User = get_user_model()


@override_settings(AXES_ENABLED=False)
class DeleteMyConversationsTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice@x.com", email="alice@x.com", password="alicepw12",
        )
        self.bob = User.objects.create_user(
            username="bob@x.com", email="bob@x.com", password="bobpw1234",
        )
        # Two convos for Alice + one for Bob.
        self.a1 = TutorConversation.objects.create(user=self.alice, title="A1")
        TutorMessage.objects.create(conversation=self.a1, role="user", content="hi")
        self.a2 = TutorConversation.objects.create(user=self.alice, title="A2")
        self.b1 = TutorConversation.objects.create(user=self.bob, title="B1")
        TutorMessage.objects.create(conversation=self.b1, role="user", content="hi")

    def test_user_can_delete_their_own_conversations(self):
        self.client.force_login(self.alice)
        url = reverse("tutor_delete_my_conversations")
        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(TutorConversation.objects.filter(user=self.alice).exists())
        # The deletion cascades to messages.
        self.assertFalse(TutorMessage.objects.filter(conversation__user=self.alice).exists())

    def test_delete_my_conversations_does_not_touch_other_users(self):
        self.client.force_login(self.alice)
        self.client.post(reverse("tutor_delete_my_conversations"))
        # Bob's conversations remain untouched.
        self.assertTrue(TutorConversation.objects.filter(user=self.bob).exists())
        self.assertTrue(TutorMessage.objects.filter(conversation__user=self.bob).exists())

    def test_anonymous_user_cannot_delete(self):
        url = reverse("tutor_delete_my_conversations")
        r = self.client.post(url)
        # @login_required redirects anonymous users.
        self.assertEqual(r.status_code, 302)
        self.assertIn("/auth/", r["Location"])
        self.assertTrue(TutorConversation.objects.filter(user=self.alice).exists())

    def test_get_request_is_rejected(self):
        """``@require_POST`` keeps this off the URL-bar — accidental
        GET via a bookmark must not wipe data."""
        self.client.force_login(self.alice)
        r = self.client.get(reverse("tutor_delete_my_conversations"))
        self.assertEqual(r.status_code, 405)
        self.assertTrue(TutorConversation.objects.filter(user=self.alice).exists())


class PurgeOldConversationsCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="purge@x.com", email="purge@x.com", password="purgepw1",
        )

    def _conversation_aged(self, days_ago: int) -> TutorConversation:
        """Create a conversation whose updated_at is ``days_ago`` in the past."""
        c = TutorConversation.objects.create(user=self.user)
        # ``auto_now`` blocks direct assignment; do it via update.
        TutorConversation.objects.filter(pk=c.pk).update(
            updated_at=timezone.now() - timedelta(days=days_ago),
        )
        c.refresh_from_db()
        return c

    def test_purge_management_command_deletes_old_conversations(self):
        old = self._conversation_aged(120)
        # default retention is 90 days
        call_command("purge_old_tutor_conversations", stdout=StringIO())
        self.assertFalse(TutorConversation.objects.filter(pk=old.pk).exists())

    def test_purge_keeps_recent_conversations(self):
        recent = self._conversation_aged(10)
        call_command("purge_old_tutor_conversations", stdout=StringIO())
        self.assertTrue(TutorConversation.objects.filter(pk=recent.pk).exists())

    def test_purge_honours_days_flag(self):
        c = self._conversation_aged(40)
        # With --days 30, the 40-day-old row should be deleted.
        call_command("purge_old_tutor_conversations", days=30, stdout=StringIO())
        self.assertFalse(TutorConversation.objects.filter(pk=c.pk).exists())

    def test_dry_run_does_not_delete(self):
        old = self._conversation_aged(120)
        call_command("purge_old_tutor_conversations", dry_run=True, stdout=StringIO())
        self.assertTrue(TutorConversation.objects.filter(pk=old.pk).exists())
