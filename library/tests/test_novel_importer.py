"""19.0D import-pipeline tests — no real PDF required.

A small ``.txt`` fixture stands in for the PDF source so the cleaner, chapter
detector, segmenter, and the command's dry-run/apply paths are all exercised
deterministically. Asserts the imported novel is NON-student-visible.
"""
from __future__ import annotations

import os
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import Book, NovelSegment
from library.services import novel_importer


User = get_user_model()


# A long sentence repeated to make chapter II exceed one segment.
_LONG = " ".join(
    [f"The black tulip grew slowly in the dark soil number {i}." for i in range(40)]
)

SAMPLE = (
    "THE BLACK TULIP\n"
    "\n"
    "I\n"
    "\n"
    "It was a bright\x00 morning in Holland�. Cornelius walked in the garden. "
    "He loved tulips very much. The soil was rich and dark. He planted a rare "
    "bulb with great hope. Every day he watched it grow.\n"
    "\n"
    "12\n"
    "\n"
    "II\n"
    "\n"
    + _LONG + "\n"
)


def _write_txt(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


class TextCleanerTests(TestCase):
    def test_cleaner_removes_bad_chars(self):
        cleaned, warnings = novel_importer.clean_text(SAMPLE)
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("�", cleaned)
        self.assertIn("null characters removed", warnings)

    def test_cleaner_drops_page_number_lines(self):
        cleaned, _ = novel_importer.clean_text(SAMPLE)
        # The standalone "12" page-number line should be gone, but the word
        # "Holland" stays.
        self.assertNotIn("\n12\n", "\n" + cleaned + "\n")
        self.assertIn("Holland", cleaned)


class ChapterDetectionTests(TestCase):
    def test_detects_two_roman_chapters(self):
        cleaned, _ = novel_importer.clean_text(SAMPLE)
        chapters, _ = novel_importer.detect_chapters(cleaned)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0]["title"], "Chapter 1")
        self.assertEqual(chapters[1]["title"], "Chapter 2")

    def test_fallback_when_no_headings(self):
        plain = "Just some text. " * 800  # ~3200 words, no headings
        chapters, warnings = novel_importer.detect_chapters(plain, fallback_words=1000)
        self.assertGreaterEqual(len(chapters), 2)
        self.assertTrue(any("falling back" in w for w in warnings))


class SegmentationTests(TestCase):
    def test_segments_respect_max_words(self):
        cleaned, _ = novel_importer.clean_text(SAMPLE)
        chapters, _ = novel_importer.detect_chapters(cleaned)
        long_chapter = chapters[1]
        segments = novel_importer.segment_text(long_chapter["body"])
        self.assertGreater(len(segments), 1)
        for seg in segments:
            # Allow one trailing sentence to nudge slightly over target, but it
            # must stay near the soft ceiling (never an entire chapter).
            self.assertLessEqual(len(seg.split()), novel_importer.SEGMENT_MAX_WORDS + 25)

    def test_estimate_seconds_scales_with_words(self):
        r1, a1 = novel_importer.estimate_seconds(200)
        r2, a2 = novel_importer.estimate_seconds(400)
        self.assertLess(r1, r2)
        self.assertLess(a1, a2)


@override_settings(AXES_ENABLED=False)
class CommandTests(TestCase):
    def test_dry_run_writes_nothing(self):
        path = _write_txt(SAMPLE)
        try:
            before = Book.objects.count()
            call_command("import_black_tulip_pdf", "--source", path, "--dry-run")
            self.assertEqual(Book.objects.count(), before)
        finally:
            os.remove(path)

    def test_apply_creates_unpublished_book(self):
        path = _write_txt(SAMPLE)
        try:
            call_command("import_black_tulip_pdf", "--source", path, "--apply")
        finally:
            os.remove(path)
        book = Book.objects.get(title=novel_importer.BOOK_TITLE)
        self.assertFalse(book.is_published)
        self.assertFalse(book.is_copyright_cleared)
        self.assertEqual(book.copyright_status, "public_domain")
        self.assertGreaterEqual(book.chapters.count(), 2)
        self.assertTrue(NovelSegment.objects.filter(chapter__book=book).exists())
        # Imported segments are unpublished.
        self.assertFalse(
            NovelSegment.objects.filter(chapter__book=book, is_published=True).exists()
        )

    def test_imported_book_not_student_visible(self):
        path = _write_txt(SAMPLE)
        try:
            call_command("import_black_tulip_pdf", "--source", path, "--apply")
        finally:
            os.remove(path)
        book = Book.objects.get(title=novel_importer.BOOK_TITLE)
        chapter = book.chapters.first()

        user = User.objects.create_user(username="r@x.com", email="r@x.com", password="pw")
        user.profile.subscription_status = "active"
        user.profile.subscription_expires_at = None
        user.profile.save()
        self.client.force_login(user)
        resp = self.client.get(reverse("library_chapter_reader", args=[chapter.pk]))
        # Not copyright-cleared → reader gate returns 404.
        self.assertEqual(resp.status_code, 404)

    def test_missing_source_raises_clean_error(self):
        with self.assertRaises(CommandError):
            call_command("import_black_tulip_pdf", "--source", "/no/such/file.pdf", "--dry-run")

    def test_replace_does_not_duplicate(self):
        path = _write_txt(SAMPLE)
        try:
            call_command("import_black_tulip_pdf", "--source", path, "--apply")
            call_command("import_black_tulip_pdf", "--source", path, "--apply", "--replace")
        finally:
            os.remove(path)
        self.assertEqual(Book.objects.filter(title=novel_importer.BOOK_TITLE).count(), 1)


class DemoStillWorksTests(TestCase):
    def test_safe_demo_seed_coexists_with_import(self):
        path = _write_txt(SAMPLE)
        try:
            call_command("seed_library_demo_black_tulip")
            call_command("import_black_tulip_pdf", "--source", path, "--apply")
        finally:
            os.remove(path)
        # Demo (cleared) and import-review (not cleared) are distinct books.
        demo = Book.objects.get(title="The Black Tulip — Demo Reader")
        review = Book.objects.get(title=novel_importer.BOOK_TITLE)
        self.assertTrue(demo.is_copyright_cleared)
        self.assertFalse(review.is_copyright_cleared)
