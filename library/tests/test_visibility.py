"""Library text activation + visibility tests (Phase 19.0H).

Covers the full-text import (Book/Chapters/Segments with text_en), the
`library_visibility_cleanup` command (dry-run is a no-op, apply only hides,
never deletes), and that hidden books vanish for students but stay visible
in Platform Admin. No PDF is required — the importer accepts a .txt source.
"""
from __future__ import annotations

import os
import tempfile
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from library.models import Book, Chapter, NovelSegment
from library.services import novel_importer
from platform_admin.tests.utils import PlatformAdminTestMixin

# Two clearly-delimited chapters with enough prose to produce segments.
_PROSE = (
    "The quiet city woke slowly under a pale and patient morning sky. "
    "Merchants opened their shutters while children ran along the canal. "
    "Every street carried the smell of bread and the sound of distant bells. "
) * 8
_TXT = f"CHAPTER 1\n\n{_PROSE}\n\nCHAPTER 2\n\n{_PROSE}\n"


def _write_txt():
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="onlenco-novel-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(_TXT)
    return path


class FullTextImportTests(TestCase):
    """Tests H1, H2, H8 (import side)."""

    def setUp(self):
        self.src = _write_txt()
        self.addCleanup(lambda: os.path.exists(self.src) and os.remove(self.src))

    def test_import_creates_book_chapters_segments_with_text_en(self):
        result = novel_importer.apply_import(self.src, replace=True)
        book = Book.objects.get(title=novel_importer.BOOK_TITLE)
        self.assertGreaterEqual(book.chapters.count(), 2)
        segs = NovelSegment.objects.filter(chapter__book=book)
        self.assertGreater(segs.count(), 0)
        for s in segs:
            self.assertTrue(s.text_en.strip())   # English text present
            self.assertEqual(s.text_ar, "")      # no translation generated
            self.assertEqual(s.arabic_summary, "")  # no summary generated

    def test_imported_book_is_hidden_and_not_cleared(self):
        novel_importer.apply_import(self.src, replace=True)
        book = Book.objects.get(title=novel_importer.BOOK_TITLE)
        self.assertFalse(book.is_published)         # not student-visible
        self.assertFalse(book.is_copyright_cleared)  # review pending

    def test_no_vocabulary_or_illustrations_generated(self):
        from library.models import NovelVocabularyHighlight, NovelIllustration
        novel_importer.apply_import(self.src, replace=True)
        book = Book.objects.get(title=novel_importer.BOOK_TITLE)
        self.assertEqual(
            NovelVocabularyHighlight.objects.filter(segment__chapter__book=book).count(), 0)
        self.assertEqual(
            NovelIllustration.objects.filter(segment__chapter__book=book).count(), 0)


class VisibilityCleanupCommandTests(TestCase):
    """Tests H3, H4, H5, H8, H9."""

    def setUp(self):
        self.keep = Book.objects.create(
            title="The Black Tulip — Full Import Review", code="BT-KEEP",
            copyright_status="public_domain", is_published=False,
        )
        Chapter.objects.create(book=self.keep, title="C1", code="BT-KEEP-C1", body="x")
        # A visible demo + a visible old book that should be hidden.
        self.demo = Book.objects.create(title="Safe Demo", code="DEMO1", is_published=True)
        self.old = Book.objects.create(title="Old Book", code="OLD1", is_published=True)

    def _run(self, *args):
        out = StringIO()
        call_command("library_visibility_cleanup", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        self._run("--keep-book", self.keep.title, "--hide-others", "--dry-run")
        self.demo.refresh_from_db(); self.old.refresh_from_db()
        self.assertTrue(self.demo.is_published)  # untouched
        self.assertTrue(self.old.is_published)

    def test_apply_hides_other_books(self):
        self._run("--keep-book", self.keep.title, "--hide-others", "--apply")
        self.demo.refresh_from_db(); self.old.refresh_from_db()
        self.assertFalse(self.demo.is_published)
        self.assertFalse(self.old.is_published)

    def test_keep_book_not_hidden_and_not_published(self):
        self._run("--keep-book-id", str(self.keep.pk), "--hide-others", "--apply")
        self.keep.refresh_from_db()
        # Kept book is left exactly as-is — neither hidden differently nor auto-published.
        self.assertFalse(self.keep.is_published)

    def test_apply_does_not_delete_anything(self):
        before = Book.objects.count()
        self._run("--keep-book", self.keep.title, "--hide-others", "--apply")
        self.assertEqual(Book.objects.count(), before)  # nothing deleted

    def test_does_not_change_copyright_clearance(self):
        self.demo.is_copyright_cleared = True
        self.demo.save(update_fields=["is_copyright_cleared"])
        self._run("--keep-book", self.keep.title, "--hide-others", "--apply")
        self.demo.refresh_from_db()
        self.assertTrue(self.demo.is_copyright_cleared)  # clearance untouched

    def test_requires_keep_book(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self._run("--hide-others", "--apply")


def _make_books():
    hidden = Book.objects.create(title="Hidden Novel", code="HID1", is_published=False)
    visible = Book.objects.create(
        title="Visible Novel", code="VIS1", is_published=True,
        copyright_status="public_domain", is_copyright_cleared=True,
    )
    return hidden, visible


class StudentVisibilityTests(TestCase):
    """Tests H6, H10 (student side)."""

    def setUp(self):
        User = get_user_model()
        self.hidden, self.visible = _make_books()
        self.student = User.objects.create_user(username="stu", password="pw")
        self.student.profile.subscription_status = "active"
        self.student.profile.save(update_fields=["subscription_status"])

    def test_student_library_list_excludes_hidden(self):
        self.client.force_login(self.student)
        body = self.client.get(reverse("library"), {"level": "all"}).content.decode()
        self.assertIn("Visible Novel", body)
        self.assertNotIn("Hidden Novel", body)

    def test_publishing_gate_still_evaluates(self):
        # The gate must keep returning a structured decision, not crash.
        from library.services.publishing import can_publish_book
        check = can_publish_book(self.hidden)
        self.assertFalse(check.allowed)          # empty book → not publishable
        self.assertTrue(len(check.reasons) > 0)  # explains why


class AdminVisibilityTests(PlatformAdminTestMixin, TestCase):
    """Test H7: Platform Admin still lists hidden books for review."""

    def setUp(self):
        super().setUp()
        self.hidden, self.visible = _make_books()

    def test_platform_admin_shows_hidden_books(self):
        self.client.force_login(self.platform_admin)
        body = self.client.get(reverse("platform_admin:library_books")).content.decode()
        self.assertIn("Hidden Novel", body)   # admin sees hidden book
        self.assertIn("Visible Novel", body)  # …and visible ones
