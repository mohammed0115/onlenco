"""Listening resume tests (Phase 19.0J).

The learner continues from where they stopped: the audio progress endpoint
persists a chunk index + offset on LibraryProgress, the listen page exposes it,
and finishing the chapter resets it.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from library.models import Book, Chapter, LibraryProgress


def _subscribe(u):
    u.profile.subscription_status = "active"
    u.profile.save(update_fields=["subscription_status"])
    return u


class ListenResumeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.book = Book.objects.create(
            title="Resume Book", code="RSMBK", is_published=True,
            is_copyright_cleared=True, copyright_status="public_domain")
        self.chapter = Chapter.objects.create(
            book=self.book, title="C1", code="RSMBK-C1", body="Hello world. More text here.")
        self.user = _subscribe(User.objects.create_user(username="r", password="pw"))
        self.prog_url = reverse("library_audio_progress", args=[self.chapter.pk])
        self.listen_url = reverse("library_chapter_listen", args=[self.chapter.pk])

    def _save(self, **payload):
        return self.client.post(self.prog_url, payload,
                                content_type="application/json")

    def test_anonymous_cannot_save(self):
        self.assertEqual(self.client.post(self.prog_url).status_code, 302)

    def test_non_subscriber_forbidden(self):
        User = get_user_model()
        plain = User.objects.create_user(username="free", password="pw")
        self.client.force_login(plain)
        self.assertEqual(self._save(chunk=2).status_code, 403)

    def test_save_and_restore_resume_point(self):
        self.client.force_login(self.user)
        self._save(chunk=3, offset=12)
        p = LibraryProgress.objects.get(user=self.user, chapter=self.chapter)
        self.assertEqual(p.last_audio_chunk, 3)
        self.assertEqual(p.last_audio_offset, 12)
        # Listen page exposes the resume point.
        body = self.client.get(self.listen_url).content.decode()
        self.assertIn("resumeBar", body)
        self.assertIn('parseInt("3", 10)', body)  # resume_chunk wired into JS

    def test_done_resets_resume_point(self):
        self.client.force_login(self.user)
        self._save(chunk=5, offset=30)
        self._save(done=True)
        p = LibraryProgress.objects.get(user=self.user, chapter=self.chapter)
        self.assertEqual(p.last_audio_chunk, 0)
        self.assertEqual(p.last_audio_offset, 0)

    def test_fresh_chapter_has_zero_resume(self):
        self.client.force_login(self.user)
        body = self.client.get(self.listen_url).content.decode()
        self.assertIn('let resumeChunk = parseInt("0", 10)', body)
