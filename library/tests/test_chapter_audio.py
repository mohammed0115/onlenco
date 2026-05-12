"""Chapter audio (listening-unit) tests."""
from __future__ import annotations

from django.test import TestCase

from library.models import Book, Chapter


class ChapterAudioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book = Book.objects.create(
            title="A0 Listening", category="short", level="A0",
            is_published=True,
        )

    def test_chapter_without_audio_is_silent(self):
        ch = Chapter.objects.create(
            book=self.book, sort_order=1, title="No audio yet", body="Hello.",
        )
        self.assertFalse(ch.has_audio)
        self.assertEqual(ch.get_audio_src(), "")

    def test_chapter_with_audio_url_renders(self):
        ch = Chapter.objects.create(
            book=self.book, sort_order=2, title="With URL", body="Hello.",
            audio_url="https://example.test/audio.mp3",
        )
        self.assertTrue(ch.has_audio)
        self.assertEqual(ch.get_audio_src(), "https://example.test/audio.mp3")

    def test_file_wins_over_url_when_both_set(self):
        """Per spec: an uploaded audio_file takes precedence over the
        external URL. The URL is the fallback, not a duplicate source."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        # Minimal "MP3" stub — validator checks extension first.
        fake_audio = SimpleUploadedFile(
            "x.mp3", b"\x00" * 100, content_type="audio/mpeg",
        )
        ch = Chapter.objects.create(
            book=self.book, sort_order=3, title="Both", body="Hello.",
            audio_file=fake_audio,
            audio_url="https://example.test/should-be-ignored.mp3",
        )
        self.assertTrue(ch.has_audio)
        # File path wins — get_audio_src returns the file's URL.
        self.assertNotEqual(
            ch.get_audio_src(),
            "https://example.test/should-be-ignored.mp3",
        )
        self.assertIn("library/audio", ch.get_audio_src())

    def test_duration_seconds_default(self):
        ch = Chapter.objects.create(
            book=self.book, sort_order=4, title="No duration", body="Hi.",
        )
        self.assertEqual(ch.duration_seconds, 0)
