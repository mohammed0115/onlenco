"""19.0C reader UI + copyright-gate + demo-seed tests.

No browser needed — these assert HTML structure, the copyright gate, and that
the seed command imports no PDF / makes no media. Reader UI, translation
toggle, vocabulary, and Arabic summary are checked as rendered HTML.
"""
from __future__ import annotations

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import (
    Book,
    Chapter,
    NovelIllustration,
    NovelSegment,
    NovelVocabularyHighlight,
)


User = get_user_model()


def _png() -> SimpleUploadedFile:
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
    return SimpleUploadedFile("ill.png", buf.getvalue(), content_type="image/png")


def _make_reader_fixture(*, cleared=True, published_segment=True):
    book = Book.objects.create(
        title="Demo Novel", category="novel", level="A2",
        is_published=True, copyright_status="adapted_original",
        is_copyright_cleared=cleared,
    )
    chapter = Chapter.objects.create(book=book, title="Ch1", body="...", sort_order=1)
    segment = NovelSegment.objects.create(
        chapter=chapter, order=1, title="A Rare Flower",
        text_en="A tulip as black as night.",
        text_ar="زهرة توليب سوداء كالليل.",
        arabic_summary="شرح عربي مختصر للمقطع.",
        is_published=published_segment,
    )
    NovelVocabularyHighlight.objects.create(
        segment=segment, word="rare", meaning_ar="نادر",
        explanation_ar="شيء قليل الوجود.",
    )
    return book, chapter, segment


@override_settings(AXES_ENABLED=False)
class ReaderCopyrightGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="s@x.com", email="s@x.com", password="pw",
        )
        self.user.profile.subscription_status = "active"
        self.user.profile.subscription_expires_at = None
        self.user.profile.save()
        self.client.force_login(self.user)

    def _url(self, chapter):
        return reverse("library_chapter_reader", args=[chapter.pk])

    def test_non_cleared_book_is_not_readable(self):
        _, chapter, _ = _make_reader_fixture(cleared=False)
        resp = self.client.get(self._url(chapter))
        self.assertEqual(resp.status_code, 404)

    def test_cleared_published_book_is_readable(self):
        _, chapter, _ = _make_reader_fixture(cleared=True)
        resp = self.client.get(self._url(chapter))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "A tulip as black as night.")

    def test_unpublished_segment_not_shown(self):
        _, chapter, _ = _make_reader_fixture(published_segment=False)
        resp = self.client.get(self._url(chapter))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "A tulip as black as night.")

    def test_pending_illustration_not_shown(self):
        _, chapter, segment = _make_reader_fixture()
        NovelIllustration.objects.create(
            segment=segment, alt_text="A black tulip",
            generation_status="needs_review",  # no file, not approved
        )
        resp = self.client.get(self._url(chapter))
        self.assertNotContains(resp, "novel_illustrations")

    def test_approved_illustration_with_file_is_shown(self):
        _, chapter, segment = _make_reader_fixture()
        NovelIllustration.objects.create(
            segment=segment, alt_text="A black tulip",
            image=_png(), generation_status="approved",
        )
        resp = self.client.get(self._url(chapter))
        self.assertContains(resp, "novel_illustrations")
        self.assertContains(resp, "A black tulip")

    def test_unsubscribed_student_redirected(self):
        self.user.profile.subscription_status = "inactive"
        self.user.profile.save()
        _, chapter, _ = _make_reader_fixture()
        resp = self.client.get(self._url(chapter))
        self.assertEqual(resp.status_code, 302)


@override_settings(AXES_ENABLED=False)
class ReaderUIContentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u@x.com", email="u@x.com", password="pw",
        )
        self.user.profile.subscription_status = "active"
        self.user.profile.subscription_expires_at = None
        self.user.profile.save()
        self.client.force_login(self.user)
        _, self.chapter, _ = _make_reader_fixture()
        self.resp = self.client.get(reverse("library_chapter_reader", args=[self.chapter.pk]))

    def test_translation_present_inside_toggle(self):
        self.assertEqual(self.resp.status_code, 200)
        self.assertContains(self.resp, 'data-testid="segment-translation"')
        self.assertContains(self.resp, "زهرة توليب سوداء كالليل.")
        # The translation lives inside a <details> element (hidden by default).
        self.assertContains(self.resp, "<details")

    def test_vocabulary_meaning_shown(self):
        self.assertContains(self.resp, 'data-testid="vocab-highlight"')
        self.assertContains(self.resp, "نادر")

    def test_arabic_summary_shown(self):
        self.assertContains(self.resp, 'data-testid="segment-summary"')
        self.assertContains(self.resp, "شرح عربي مختصر للمقطع.")

    def test_library_nav_link_present(self):
        self.assertContains(self.resp, 'data-testid="header-library-link"')

    def test_reader_is_mobile_friendly_structure(self):
        self.assertContains(self.resp, "max-w-3xl")
        self.assertContains(self.resp, 'data-testid="reader-segment"')

    def test_listen_link_reuses_natural_reader(self):
        self.assertContains(self.resp, reverse("library_chapter_listen", args=[self.chapter.pk]))


class DemoSeedCommandTests(TestCase):
    def test_seed_creates_safe_demo_without_pdf(self):
        call_command("seed_library_demo_black_tulip")
        book = Book.objects.get(title="The Black Tulip — Demo Reader")
        self.assertEqual(book.copyright_status, "adapted_original")
        self.assertTrue(book.is_copyright_cleared)
        self.assertTrue(book.is_school_curriculum)
        self.assertEqual(book.school_country, "Sudan")
        # No PDF file is imported/used.
        self.assertFalse(bool(book.pdf))

    def test_seed_creates_segments_and_vocab(self):
        call_command("seed_library_demo_black_tulip")
        book = Book.objects.get(title="The Black Tulip — Demo Reader")
        chapter = book.chapters.get(sort_order=1)
        segments = list(chapter.segments.all())
        self.assertGreaterEqual(len(segments), 3)
        for seg in segments:
            self.assertTrue(seg.text_en)
            self.assertTrue(seg.text_ar)
            self.assertTrue(seg.arabic_summary)
            self.assertTrue(seg.vocabulary_highlights.exists())

    def test_seed_illustration_is_not_student_visible(self):
        call_command("seed_library_demo_black_tulip")
        for ill in NovelIllustration.objects.all():
            self.assertFalse(ill.is_student_visible)

    def test_seed_is_idempotent(self):
        call_command("seed_library_demo_black_tulip")
        call_command("seed_library_demo_black_tulip")
        self.assertEqual(Book.objects.filter(title="The Black Tulip — Demo Reader").count(), 1)
