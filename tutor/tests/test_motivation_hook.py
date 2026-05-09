"""Verify the tutor send view credits speaking_minutes/writing_attempts and
runs the motivation engine."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from motivation.models import LearnerActivitySnapshot, UserXP
from tutor.models import TutorConversation, TutorMessage

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class TutorMotivationHookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="t@x.com", email="t@x.com", password="pw"
        )
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.client.login(username="t@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user, topic="grammar")

    def _send(self, body="hello tutor", speaking_seconds=0):
        with patch("tutor.views.chat", return_value="Hi back."):
            return self.client.post(
                reverse("tutor_send", args=[self.conv.pk]),
                {"message": body, "speaking_seconds": str(speaking_seconds)},
            )

    def test_writing_attempt_credited_per_message(self):
        self._send("first")
        snap = LearnerActivitySnapshot.objects.get(user=self.user, date=timezone.localdate())
        self.assertEqual(snap.writing_attempts, 1)
        self._send("second")
        snap.refresh_from_db()
        self.assertEqual(snap.writing_attempts, 2)

    def test_speaking_seconds_become_minutes(self):
        self._send("voice", speaking_seconds=120)
        snap = LearnerActivitySnapshot.objects.get(user=self.user, date=timezone.localdate())
        self.assertEqual(snap.speaking_minutes, 2)

    def test_motivation_engine_creates_user_xp(self):
        self._send("hi")
        self.assertTrue(UserXP.objects.filter(user=self.user).exists())

    def test_speaking_seconds_capped_at_one_hour(self):
        self._send("ramble", speaking_seconds=999999)
        snap = LearnerActivitySnapshot.objects.get(user=self.user, date=timezone.localdate())
        self.assertLessEqual(snap.speaking_minutes, 60)
