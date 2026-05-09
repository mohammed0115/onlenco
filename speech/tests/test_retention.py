"""Audio retention: cleanup command + voice-history endpoints."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from speech.models import SpeakingAttempt

User = get_user_model()


def _attempt(user, age_days=0, with_audio=True):
    """Create a SpeakingAttempt aged `age_days` in the past."""
    audio = (
        SimpleUploadedFile("rec.webm", b"x" * 1024, content_type="audio/webm")
        if with_audio else None
    )
    a = SpeakingAttempt.objects.create(
        user=user, transcript="hi", duration_seconds=2,
        confidence=1.0, source="tutor", audio_file=audio,
    )
    if age_days:
        SpeakingAttempt.objects.filter(pk=a.pk).update(
            created_at=timezone.now() - timedelta(days=age_days),
        )
        a.refresh_from_db()
    return a


class CleanOldVoiceRecordingsCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="r@x.com", password="pw")

    @override_settings(SPEECH_AUDIO_RETENTION_DAYS=7)
    def test_purges_audio_older_than_retention_window(self):
        old = _attempt(self.user, age_days=10)
        fresh = _attempt(self.user, age_days=1)
        out = StringIO()
        call_command("clean_old_voice_recordings", stdout=out)
        old.refresh_from_db()
        fresh.refresh_from_db()
        self.assertFalse(old.audio_file)
        self.assertTrue(fresh.audio_file)
        self.assertIn("Cleaned 1/1", out.getvalue())

    @override_settings(SPEECH_AUDIO_RETENTION_DAYS=7)
    def test_dry_run_does_not_touch_files(self):
        old = _attempt(self.user, age_days=10)
        call_command("clean_old_voice_recordings", "--dry-run", stdout=StringIO())
        old.refresh_from_db()
        self.assertTrue(old.audio_file)

    @override_settings(SPEECH_AUDIO_RETENTION_DAYS=7)
    def test_keeps_transcript_after_audio_purge(self):
        old = _attempt(self.user, age_days=10)
        call_command("clean_old_voice_recordings", stdout=StringIO())
        old.refresh_from_db()
        self.assertEqual(old.transcript, "hi")  # transcript stays
        self.assertEqual(old.duration_seconds, 2)

    def test_idempotent(self):
        _attempt(self.user, age_days=0, with_audio=False)
        out = StringIO()
        call_command("clean_old_voice_recordings", stdout=out)
        self.assertIn("0 cleaned", out.getvalue())


@override_settings(AXES_ENABLED=False)
class VoiceHistoryEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vh@x.com", password="pw")
        self.client.login(username="vh@x.com", password="pw")
        self.url = reverse("api_tutor_voice_history")

    def test_anonymous_get_returns_401(self):
        self.client.logout()
        r = self.client.get(self.url)
        self.assertIn(r.status_code, (401, 403))

    def test_user_only_sees_own_attempts(self):
        other = User.objects.create_user(username="other-vh@x.com", password="pw")
        _attempt(self.user)
        _attempt(other)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["count"], 1)

    def test_delete_clears_audio_keeps_transcript(self):
        a = _attempt(self.user)
        self.assertTrue(a.audio_file)
        r = self.client.delete(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["deleted"], 1)
        a.refresh_from_db()
        self.assertFalse(a.audio_file)
        self.assertEqual(a.transcript, "hi")

    def test_delete_does_not_touch_other_users_history(self):
        other = User.objects.create_user(username="o2@x.com", password="pw")
        mine = _attempt(self.user)
        theirs = _attempt(other)
        self.client.delete(self.url)
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertFalse(mine.audio_file)
        self.assertTrue(theirs.audio_file)
