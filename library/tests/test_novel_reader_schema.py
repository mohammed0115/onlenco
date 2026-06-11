"""Focused 19.0B schema tests for the Interactive Novel Reader MVP.

Locks the additive structure only — no reader UI, no content, no media
generation. Verifies copyright defaults, segment ordering/uniqueness,
vocabulary highlights without offsets, and the illustration approval gate.
"""
from __future__ import annotations

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase

from library.models import (
    Book,
    Chapter,
    NovelIllustration,
    NovelSegment,
    NovelVocabularyHighlight,
)


def _png() -> SimpleUploadedFile:
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
    return SimpleUploadedFile("ill.png", buf.getvalue(), content_type="image/png")


class BookCopyrightDefaultsTests(TestCase):
    def test_new_book_defaults_are_conservative(self):
        book = Book.objects.create(title="Demo", category="novel", level="A1")
        self.assertEqual(book.copyright_status, "unknown")
        self.assertFalse(book.is_copyright_cleared)
        self.assertEqual(book.content_language, "en")
        self.assertFalse(book.is_school_curriculum)

    def test_book_can_be_public_domain_and_cleared(self):
        book = Book.objects.create(
            title="The Black Tulip", category="novel", level="B1",
            copyright_status="public_domain", is_copyright_cleared=True,
            source_title="The Black Tulip (Project Gutenberg)",
            target_cefr_level="B1", is_school_curriculum=True, school_country="Sudan",
        )
        self.assertEqual(book.copyright_status, "public_domain")
        self.assertTrue(book.is_copyright_cleared)
        self.assertEqual(book.target_cefr_level, "B1")


class NovelSegmentTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(title="Demo", category="novel", level="A1")
        self.chapter = Chapter.objects.create(book=self.book, title="Ch1", body="...", sort_order=1)

    def _seg(self, order, text="Hello."):
        return NovelSegment.objects.create(chapter=self.chapter, order=order, text_en=text)

    def test_segments_order_by_chapter_then_order(self):
        self._seg(2, "second")
        self._seg(1, "first")
        ordered = list(self.chapter.segments.values_list("order", flat=True))
        self.assertEqual(ordered, [1, 2])

    def test_unique_chapter_order(self):
        self._seg(1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._seg(1)

    def test_arabic_fields_optional(self):
        seg = self._seg(1)
        self.assertEqual(seg.text_ar, "")
        self.assertEqual(seg.arabic_summary, "")
        self.assertFalse(seg.is_published)


class NovelVocabularyHighlightTests(TestCase):
    def setUp(self):
        book = Book.objects.create(title="Demo", category="novel", level="A1")
        chapter = Chapter.objects.create(book=book, title="Ch1", body="...", sort_order=1)
        self.segment = NovelSegment.objects.create(chapter=chapter, order=1, text_en="A tulip.")

    def test_highlight_links_to_segment(self):
        h = NovelVocabularyHighlight.objects.create(
            segment=self.segment, word="tulip", meaning_ar="زهرة التوليب",
        )
        self.assertEqual(h.segment_id, self.segment.id)
        self.assertIn(h, self.segment.vocabulary_highlights.all())

    def test_highlight_does_not_require_offsets(self):
        h = NovelVocabularyHighlight.objects.create(
            segment=self.segment, word="tulip", meaning_ar="توليب",
        )
        self.assertIsNone(h.start_offset)
        self.assertIsNone(h.end_offset)
        self.assertTrue(h.is_active)


class NovelIllustrationLifecycleTests(TestCase):
    def setUp(self):
        book = Book.objects.create(title="Demo", category="novel", level="A1")
        chapter = Chapter.objects.create(book=book, title="Ch1", body="...", sort_order=1)
        self.segment = NovelSegment.objects.create(chapter=chapter, order=1, text_en="A tulip.")

    def test_pending_illustration_not_student_visible(self):
        ill = NovelIllustration.objects.create(segment=self.segment, description="a black tulip")
        self.assertEqual(ill.generation_status, "pending_generation")
        self.assertFalse(ill.is_student_visible)

    def test_approved_with_file_is_student_visible(self):
        ill = NovelIllustration.objects.create(
            segment=self.segment, description="a black tulip",
            image=_png(), generation_status="approved",
        )
        self.assertTrue(ill.is_student_visible)

    def test_approved_without_file_is_not_student_visible(self):
        ill = NovelIllustration.objects.create(
            segment=self.segment, description="x", generation_status="approved",
        )
        self.assertFalse(ill.is_student_visible)

    def test_rejected_with_file_is_not_student_visible(self):
        ill = NovelIllustration.objects.create(
            segment=self.segment, image=_png(), generation_status="rejected",
        )
        self.assertFalse(ill.is_student_visible)


class NovelAdminSmokeTests(TestCase):
    def test_novel_models_registered_in_admin(self):
        from django.contrib import admin as dj_admin
        for model in (NovelSegment, NovelVocabularyHighlight, NovelIllustration):
            self.assertTrue(dj_admin.site.is_registered(model), model.__name__)

    def test_book_admin_has_copyright_filters(self):
        from django.contrib import admin as dj_admin
        book_admin = dj_admin.site._registry[Book]
        for f in ("copyright_status", "is_copyright_cleared", "is_school_curriculum"):
            self.assertIn(f, book_admin.list_filter)
