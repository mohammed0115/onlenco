"""Platform Admin — Chapter audio upload tests (Phase 19.0F).

Uploads go to a temp MEDIA_ROOT (never the repo). Verifies permissions,
validation, status, and that uploading never publishes or changes copyright.
"""
from __future__ import annotations

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import Book, Chapter

from .utils import PlatformAdminTestMixin

_MEDIA = tempfile.mkdtemp(prefix="onlenco-test-media-")


def _book_with_chapter(**overrides):
    defaults = dict(title="Audio Book", code="AUDBK", copyright_status="unknown",
                    is_copyright_cleared=False, is_published=False)
    defaults.update(overrides)
    book = Book.objects.create(**defaults)
    chapter = Chapter.objects.create(book=book, title="Chapter 1", code="AUDBK-C1")
    return book, chapter


def _mp3(name="ch.mp3", size=2048):
    return SimpleUploadedFile(name, b"ID3" + b"\x00" * size, content_type="audio/mpeg")


@override_settings(MEDIA_ROOT=_MEDIA)
class ChapterAudioTests(PlatformAdminTestMixin, TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.book, self.chapter = _book_with_chapter()
        self.audio_url = reverse("platform_admin:library_chapter_audio", args=[self.chapter.pk])

    # --- permissions ---
    def test_anonymous_redirected(self):
        r = self.client.get(self.audio_url)
        self.assertEqual(r.status_code, 302)

    def test_student_forbidden(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.audio_url).status_code, 403)

    def test_admin_sees_audio_status_in_book_detail(self):
        self.client.force_login(self.platform_admin)
        body = self.client.get(reverse("platform_admin:library_book", args=[self.book.pk])).content.decode()
        self.assertIn(self.audio_url, body)  # link to the chapter audio page
        self.assertIn("badge-red", body)     # "no audio" badge (lang-independent)

    def test_view_only_cannot_upload(self):
        # read-only admin has library.view (via VIEW_CAPS) but not manage.
        self.client.force_login(self.readonly_admin)
        self.assertEqual(self.client.get(self.audio_url).status_code, 200)  # can view
        r = self.client.post(self.audio_url, {"audio_file": _mp3(), "duration_seconds": 10})
        self.assertEqual(r.status_code, 403)  # cannot upload
        self.chapter.refresh_from_db()
        self.assertFalse(self.chapter.audio_file)

    # --- upload + validation ---
    def test_manage_can_upload_mp3(self):
        self.client.force_login(self.platform_admin)
        r = self.client.post(self.audio_url, {"audio_file": _mp3(), "duration_seconds": 30})
        self.assertEqual(r.status_code, 302)
        self.chapter.refresh_from_db()
        self.assertTrue(self.chapter.audio_file)
        self.assertEqual(self.chapter.duration_seconds, 30)

    def test_pdf_rejected(self):
        self.client.force_login(self.platform_admin)
        self.client.post(self.audio_url, {
            "audio_file": SimpleUploadedFile("x.pdf", b"%PDF-1.4", content_type="application/pdf"),
        })
        self.chapter.refresh_from_db()
        self.assertFalse(self.chapter.audio_file)

    def test_disallowed_extension_rejected(self):
        self.client.force_login(self.platform_admin)
        self.client.post(self.audio_url, {
            "audio_file": SimpleUploadedFile("x.txt", b"hello", content_type="text/plain"),
        })
        self.chapter.refresh_from_db()
        self.assertFalse(self.chapter.audio_file)

    @override_settings(LIBRARY_CHAPTER_AUDIO_MAX_MB=1)
    def test_too_large_rejected(self):
        self.client.force_login(self.platform_admin)
        big = SimpleUploadedFile("big.mp3", b"ID3" + b"\x00" * (2 * 1024 * 1024), content_type="audio/mpeg")
        self.client.post(self.audio_url, {"audio_file": big})
        self.chapter.refresh_from_db()
        self.assertFalse(self.chapter.audio_file)

    def test_replace_audio(self):
        self.client.force_login(self.platform_admin)
        self.client.post(self.audio_url, {"audio_file": _mp3("first.mp3")})
        self.chapter.refresh_from_db()
        first = self.chapter.audio_file.name
        self.client.post(self.audio_url, {"audio_file": _mp3("second.mp3")})
        self.chapter.refresh_from_db()
        self.assertTrue(self.chapter.audio_file)
        self.assertIn("second", self.chapter.audio_file.name)
        self.assertNotEqual(self.chapter.audio_file.name, first)

    def test_remove_audio(self):
        self.client.force_login(self.platform_admin)
        self.client.post(self.audio_url, {"audio_file": _mp3()})
        self.chapter.refresh_from_db()
        self.assertTrue(self.chapter.audio_file)
        self.client.post(reverse("platform_admin:library_chapter_audio_remove", args=[self.chapter.pk]))
        self.chapter.refresh_from_db()
        self.assertFalse(self.chapter.audio_file)

    # --- safety: upload never publishes / changes copyright ---
    def test_upload_does_not_publish_or_change_copyright(self):
        self.client.force_login(self.platform_admin)
        self.client.post(self.audio_url, {"audio_file": _mp3()})
        self.book.refresh_from_db()
        self.assertFalse(self.book.is_published)
        self.assertFalse(self.book.is_copyright_cleared)
        self.assertEqual(self.book.copyright_status, "unknown")

    # --- dashboard counts ---
    def test_dashboard_audio_counts(self):
        self.client.force_login(self.platform_admin)
        self.client.post(self.audio_url, {"audio_file": _mp3()})
        r = self.client.get(reverse("platform_admin:library"))
        self.assertGreaterEqual(r.context["stats"]["chapters_with_audio"], 1)
        self.assertIn("chapters_missing_audio", r.context["stats"])

    def test_storage_path_under_media_library(self):
        self.client.force_login(self.platform_admin)
        self.client.post(self.audio_url, {"audio_file": _mp3()})
        self.chapter.refresh_from_db()
        self.assertTrue(self.chapter.audio_file.name.startswith("library/audio/"))


@override_settings(MEDIA_ROOT=_MEDIA)
class ChapterListenIntegrationTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        self.book, self.chapter = _book_with_chapter(
            title="Listen Book", code="LSNBK", is_published=True, is_copyright_cleared=True,
            copyright_status="public_domain")
        self.chapter.code = "LSNBK-C1"
        self.chapter.body = "Hello world."
        self.chapter.save(update_fields=["code", "body"])
        self.user = get_user_model().objects.create_user(username="listener", password="pw")
        self.user.profile.subscription_status = "active"
        self.user.profile.save(update_fields=["subscription_status"])
        self.client.force_login(self.user)
        self.listen_url = reverse("library_chapter_listen", args=[self.chapter.pk])

    def test_listen_uses_uploaded_audio_when_present(self):
        self.chapter.audio_file.save("rec.mp3", _mp3(), save=True)
        body = self.client.get(self.listen_url).content.decode()
        self.assertIn(self.chapter.audio_file.url, body)  # PRERECORDED wired

    def test_listen_falls_back_when_no_audio(self):
        r = self.client.get(self.listen_url)
        self.assertEqual(r.status_code, 200)
        self.assertIn('const PRERECORDED = "";', r.content.decode())  # empty → TTS fallback
