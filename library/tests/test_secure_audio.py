"""Secure library audio delivery tests (Phase 19.0G).

Verifies that an admin-uploaded chapter recording is served only through a
subscription- + publish/copyright- + session-gated stream route, and that
the raw MEDIA_URL is never exposed in the student page. Uploads use a temp
MEDIA_ROOT (never the repo).
"""
from __future__ import annotations

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import Book, Chapter
from subscriptions.models import LibraryAudioSession

_MEDIA = tempfile.mkdtemp(prefix="onlenco-test-secure-audio-")


def _mp3(name="ch.mp3", size=2048):
    return SimpleUploadedFile(name, b"ID3" + b"\x00" * size, content_type="audio/mpeg")


def _subscribe(user):
    user.profile.subscription_status = "active"
    user.profile.save(update_fields=["subscription_status"])
    return user


@override_settings(MEDIA_ROOT=_MEDIA)
class SecureAudioStreamTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.book = Book.objects.create(
            title="Stream Book", code="STRMBK", copyright_status="public_domain",
            is_copyright_cleared=True, is_published=True,
        )
        self.chapter = Chapter.objects.create(
            book=self.book, title="Chapter 1", code="STRMBK-C1", body="Hello.",
        )
        self.chapter.audio_file.save("rec.mp3", _mp3(), save=True)
        self.user = _subscribe(User.objects.create_user(username="reader", password="pw"))
        self.other = _subscribe(User.objects.create_user(username="other", password="pw"))
        self.stream_url = reverse("library_audio_stream", args=[self.chapter.pk])
        self.listen_url = reverse("library_chapter_listen", args=[self.chapter.pk])

    def _session_for(self, user, chapter=None):
        return LibraryAudioSession.objects.create(
            user=user, chapter_id=(chapter or self.chapter).pk, status="in_progress",
        )

    # --- HTML must not expose raw URL (tests G1 + G11) ---
    def test_student_html_has_no_raw_media_url(self):
        self.client.force_login(self.user)
        body = self.client.get(self.listen_url).content.decode()
        self.assertNotIn(self.chapter.audio_file.url, body)  # raw MEDIA_URL absent
        self.assertNotIn("/media/library/audio/", body)      # no media path leaked
        self.assertIn(self.stream_url, body)                 # secure route present

    # --- access control (tests G2-G5) ---
    def test_anonymous_cannot_stream(self):
        r = self.client.get(self.stream_url)
        self.assertEqual(r.status_code, 302)  # login redirect

    def test_non_subscriber_cannot_stream(self):
        User = get_user_model()
        plain = User.objects.create_user(username="free", password="pw")
        self.client.force_login(plain)
        s = self._session_for(plain)
        r = self.client.get(self.stream_url, {"s": s.pk})
        self.assertEqual(r.status_code, 403)

    def test_unpublished_book_not_streamable(self):
        self.book.is_published = False
        self.book.save(update_fields=["is_published"])
        self.client.force_login(self.user)
        s = self._session_for(self.user)
        r = self.client.get(self.stream_url, {"s": s.pk})
        self.assertEqual(r.status_code, 404)

    def test_non_copyright_cleared_not_streamable(self):
        self.book.is_copyright_cleared = False
        self.book.save(update_fields=["is_copyright_cleared"])
        self.client.force_login(self.user)
        s = self._session_for(self.user)
        r = self.client.get(self.stream_url, {"s": s.pk})
        self.assertEqual(r.status_code, 404)

    # --- happy path (test G6) ---
    def test_subscribed_with_session_can_stream(self):
        self.client.force_login(self.user)
        s = self._session_for(self.user)
        r = self.client.get(self.stream_url, {"s": s.pk})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "audio/mpeg")
        self.assertIn("inline", r["Content-Disposition"])
        self.assertIn("no-store", r["Cache-Control"])

    # --- session / token validation (tests G7-G9) ---
    def test_missing_or_invalid_session_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.stream_url).status_code, 403)             # none
        self.assertEqual(self.client.get(self.stream_url, {"s": "abc"}).status_code, 403)  # non-int
        self.assertEqual(self.client.get(self.stream_url, {"s": 999999}).status_code, 403)  # unknown

    def test_other_users_session_rejected(self):
        self.client.force_login(self.user)
        s = self._session_for(self.other)  # session belongs to someone else
        r = self.client.get(self.stream_url, {"s": s.pk})
        self.assertEqual(r.status_code, 403)

    def test_finished_session_rejected(self):
        self.client.force_login(self.user)
        s = self._session_for(self.user)
        s.status = "completed"
        s.save(update_fields=["status"])
        r = self.client.get(self.stream_url, {"s": s.pk})
        self.assertEqual(r.status_code, 403)

    def test_chapter_without_audio_file_404(self):
        ch = Chapter.objects.create(book=self.book, title="No audio", code="STRMBK-C2")
        url = reverse("library_audio_stream", args=[ch.pk])
        self.client.force_login(self.user)
        s = self._session_for(self.user, chapter=ch)
        r = self.client.get(url, {"s": s.pk})
        self.assertEqual(r.status_code, 404)

    # --- fallback intact (test G12) ---
    def test_natural_reader_fallback_when_no_audio(self):
        ch = Chapter.objects.create(book=self.book, title="No audio", code="STRMBK-C3", body="Hi.")
        self.client.force_login(self.user)
        r = self.client.get(reverse("library_chapter_listen", args=[ch.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('const STREAM_URL = "";', r.content.decode())


from platform_admin.tests.utils import PlatformAdminTestMixin  # noqa: E402


@override_settings(MEDIA_ROOT=_MEDIA)
class AdminAudioPreviewTests(PlatformAdminTestMixin, TestCase):
    """Test G13: Platform Admin preview is staff-gated and not a raw URL."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.book = Book.objects.create(title="Prev", code="PRVBK", is_published=False)
        self.chapter = Chapter.objects.create(book=self.book, title="C1", code="PRVBK-C1")
        self.chapter.audio_file.save("rec.mp3", _mp3(), save=True)
        self.preview_url = reverse(
            "platform_admin:library_chapter_audio_preview", args=[self.chapter.pk]
        )

    def test_admin_can_preview(self):
        self.client.force_login(self.platform_admin)
        r = self.client.get(self.preview_url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "audio/mpeg")

    def test_student_cannot_preview(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.preview_url).status_code, 403)

    def test_anonymous_cannot_preview(self):
        self.assertEqual(self.client.get(self.preview_url).status_code, 302)
