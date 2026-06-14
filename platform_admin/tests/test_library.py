"""Platform Admin — Library Management tests (Phase 19.0E).

Tests the CUSTOM control-center UI (NOT Django admin): permissions, dashboard,
book list/review, the publishing gate, segment/vocab/illustration review, and
that unsafe content never reaches students.
"""
from __future__ import annotations

from django.urls import reverse

from library.models import (
    Book, Chapter, NovelIllustration, NovelSegment, NovelVocabularyHighlight,
)
from library.services.publishing import can_publish_book

from .utils import PlatformAdminTestMixin
from django.test import TestCase


def _publishable_book(**overrides):
    """A book that passes every publish-gate condition, unless overridden."""
    defaults = dict(
        title="The Test Tulip", copyright_status="public_domain",
        is_copyright_cleared=True, is_published=False, target_cefr_level="A2",
    )
    defaults.update(overrides)
    # Explicit unique code so paired books in one test don't collide.
    defaults.setdefault("code", "TBK-" + ((defaults["title"] or "x").replace(" ", "")[:12] or "x"))
    book = Book.objects.create(**defaults)
    chapter = Chapter.objects.create(book=book, title="Chapter 1")
    NovelSegment.objects.create(
        chapter=chapter, order=1, text_en="A tulip as black as night.",
        is_published=True)
    return book


class LibraryPermissionTests(PlatformAdminTestMixin, TestCase):
    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("platform_admin:library"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/auth/", r["Location"])

    def test_student_forbidden(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("platform_admin:library")).status_code, 403)

    def test_teacher_without_library_cap_forbidden(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("platform_admin:library")).status_code, 403)

    def test_platform_admin_can_open_dashboard(self):
        self.client.force_login(self.platform_admin)
        self.assertEqual(self.client.get(reverse("platform_admin:library")).status_code, 200)

    def test_academic_admin_can_open_dashboard(self):
        self.client.force_login(self.academic_admin)
        self.assertEqual(self.client.get(reverse("platform_admin:library")).status_code, 200)

    def test_nav_link_shown_to_admin(self):
        self.client.force_login(self.platform_admin)
        body = self.client.get(reverse("platform_admin:library")).content.decode()
        self.assertIn(reverse("platform_admin:library"), body)
        self.assertIn("إدارة المكتبة", body)  # bilingual nav label present


class LibraryDashboardTests(PlatformAdminTestMixin, TestCase):
    def test_dashboard_counts(self):
        _publishable_book(title="Pub", is_published=True)
        Book.objects.create(title="Draft", code="DRAFTBK", is_published=False, is_copyright_cleared=False)
        self.client.force_login(self.platform_admin)
        r = self.client.get(reverse("platform_admin:library"))
        self.assertEqual(r.context["stats"]["total_books"], 2)
        self.assertEqual(r.context["stats"]["published_books"], 1)
        self.assertGreaterEqual(r.context["stats"]["needs_copyright"], 1)


class LibraryBooksListTests(PlatformAdminTestMixin, TestCase):
    def test_list_shows_book_and_status(self):
        _publishable_book(title="Listed Book")
        self.client.force_login(self.platform_admin)
        body = self.client.get(reverse("platform_admin:library_books")).content.decode()
        self.assertIn("Listed Book", body)

    def test_not_cleared_book_shows_needs_review(self):
        Book.objects.create(title="Uncleared", code="UNCLR", is_copyright_cleared=False, copyright_status="unknown")
        self.client.force_login(self.platform_admin)
        body = self.client.get(reverse("platform_admin:library_books")).content.decode()
        self.assertIn("Uncleared", body)
        self.assertIn("badge-red", body)  # the not-cleared / needs-review badge (lang-independent)


class PublishingGateTests(TestCase):
    def test_unknown_copyright_blocks(self):
        book = _publishable_book(copyright_status="unknown")
        self.assertFalse(can_publish_book(book).allowed)

    def test_not_cleared_blocks(self):
        book = _publishable_book(is_copyright_cleared=False)
        self.assertFalse(can_publish_book(book).allowed)

    def test_no_chapters_blocks(self):
        book = Book.objects.create(
            title="Empty", copyright_status="public_domain", is_copyright_cleared=True)
        check = can_publish_book(book)
        self.assertFalse(check.allowed)
        self.assertTrue(any("chapter" in r.lower() for r in check.reasons))

    def test_no_published_segments_blocks(self):
        book = Book.objects.create(
            title="NoSeg", copyright_status="public_domain", is_copyright_cleared=True)
        ch = Chapter.objects.create(book=book, title="C1")
        NovelSegment.objects.create(chapter=ch, order=1, text_en="x", is_published=False)
        self.assertFalse(can_publish_book(book).allowed)

    def test_empty_title_blocks(self):
        book = _publishable_book(title="")
        self.assertFalse(can_publish_book(book).allowed)

    def test_full_book_allowed(self):
        book = _publishable_book()
        check = can_publish_book(book)
        self.assertTrue(check.allowed, check.reasons)
        self.assertEqual(check.reasons, [])

    def test_licensed_needs_source(self):
        book = _publishable_book(copyright_status="licensed")
        self.assertFalse(can_publish_book(book).allowed)
        book.license_notes = "Permission granted by publisher."
        book.save(update_fields=["license_notes"])
        self.assertTrue(can_publish_book(book).allowed)


class PublishActionTests(PlatformAdminTestMixin, TestCase):
    def test_publish_blocked_when_incomplete(self):
        book = _publishable_book(copyright_status="unknown")  # not publishable
        self.client.force_login(self.platform_admin)
        self.client.post(reverse("platform_admin:library_book_action", args=[book.pk, "publish"]))
        book.refresh_from_db()
        self.assertFalse(book.is_published)

    def test_publish_when_complete(self):
        book = _publishable_book()
        self.client.force_login(self.platform_admin)
        self.client.post(reverse("platform_admin:library_book_action", args=[book.pk, "publish"]))
        book.refresh_from_db()
        self.assertTrue(book.is_published)

    def test_unpublish_hides(self):
        book = _publishable_book(is_published=True)
        self.client.force_login(self.platform_admin)
        self.client.post(reverse("platform_admin:library_book_action", args=[book.pk, "unpublish"]))
        book.refresh_from_db()
        self.assertFalse(book.is_published)

    def test_student_cannot_publish(self):
        book = _publishable_book()
        self.client.force_login(self.student)
        r = self.client.post(reverse("platform_admin:library_book_action", args=[book.pk, "publish"]))
        self.assertEqual(r.status_code, 403)
        book.refresh_from_db()
        self.assertFalse(book.is_published)


class SegmentVocabIllustrationTests(PlatformAdminTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.book = _publishable_book()
        self.segment = NovelSegment.objects.filter(chapter__book=self.book).first()

    def test_cannot_publish_empty_segment(self):
        seg = NovelSegment.objects.create(
            chapter=self.segment.chapter, order=2, text_en="", is_published=False)
        self.client.force_login(self.platform_admin)
        self.client.post(reverse("platform_admin:library_segment", args=[seg.pk]), {
            "title": "", "text_en": "", "text_ar": "", "arabic_summary": "",
            "cefr_level": "", "estimated_reading_seconds": 0,
            "estimated_audio_seconds": 0, "is_published": "on",
        })
        seg.refresh_from_db()
        self.assertFalse(seg.is_published)  # form rejected the empty publish

    def test_vocab_review_updates_meaning(self):
        v = NovelVocabularyHighlight.objects.create(
            segment=self.segment, word="tulip", meaning_ar="خزامى")
        self.client.force_login(self.platform_admin)
        self.client.post(reverse("platform_admin:library_vocab_edit", args=[v.pk]), {
            "meaning_ar": "زهرة التوليب", "explanation_ar": "نوع زهرة",
            "example_sentence": "A black tulip.", "cefr_level": "A2", "is_active": "on",
        })
        v.refresh_from_db()
        self.assertEqual(v.meaning_ar, "زهرة التوليب")
        self.assertEqual(v.explanation_ar, "نوع زهرة")

    def test_pending_illustration_not_student_visible(self):
        il = NovelIllustration.objects.create(segment=self.segment, description="a tulip")
        self.assertFalse(il.is_student_visible)  # pending_generation + no image


class StudentReaderGateTests(TestCase):
    def test_unpublished_book_reader_404(self):
        book = _publishable_book(is_published=False, is_copyright_cleared=True)
        chapter = book.chapters.first()
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user(username="reader", password="pw")
        u.profile.subscription_status = "active"
        u.profile.save(update_fields=["subscription_status"])
        self.client.force_login(u)
        # The student novel reader requires is_published AND is_copyright_cleared.
        r = self.client.get(reverse("library_chapter_reader", args=[chapter.pk]))
        self.assertEqual(r.status_code, 404)
