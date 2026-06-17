"""Novel Import Wizard tests (Phase 19.0I).

Covers permissions, upload validation, analyze (dry-run), apply (hidden book),
OCR detection, idempotency, and failure handling. Uses a temp MEDIA_ROOT and
synthetic TXT/PDF bytes — never the real Black Tulip PDF.
"""
from __future__ import annotations

import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from library.models import Book, LibraryImportJob, NovelSegment

from platform_admin.tests.utils import PlatformAdminTestMixin

_MEDIA = tempfile.mkdtemp(prefix="onlenco-test-import-")

# Two chapters with enough prose to yield segments.
_PROSE = (
    "The quiet city woke slowly under a pale and patient morning sky. "
    "Merchants opened their shutters while the children ran along the canal. "
    "Every street carried the smell of warm bread and the sound of bells. "
) * 8
_TXT_BYTES = f"CHAPTER 1\n\n{_PROSE}\n\nCHAPTER 2\n\n{_PROSE}\n".encode("utf-8")


def _txt(name="novel.txt", body=_TXT_BYTES):
    return SimpleUploadedFile(name, body, content_type="text/plain")


def _pdf_with_text():
    return SimpleUploadedFile("novel.pdf", b"%PDF-1.4 dummy", content_type="application/pdf")


def _blank_pdf_bytes():
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


@override_settings(MEDIA_ROOT=_MEDIA)
class NovelImportWizardTests(PlatformAdminTestMixin, TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.list_url = reverse("platform_admin:library_imports")
        self.new_url = reverse("platform_admin:library_import_new")

    def _make_job(self, upload=None, status="uploaded"):
        job = LibraryImportJob(status=status, source_format="txt",
                               original_filename="novel.txt")
        job.source_file.save("novel.txt", upload or _txt(), save=False)
        job.save()
        return job

    # --- permissions (H1-H4 / L1-L5) ---
    def test_admin_sees_import_link_on_dashboard(self):
        self.client.force_login(self.platform_admin)
        body = self.client.get(reverse("platform_admin:library")).content.decode()
        self.assertIn(self.list_url, body)

    def test_student_cannot_enter_wizard(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.client.get(self.new_url).status_code, 403)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 302)

    def test_teacher_without_library_cap_forbidden(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_view_only_cannot_upload_or_apply(self):
        self.client.force_login(self.readonly_admin)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)  # can view
        r = self.client.post(self.new_url, {"source_file": _txt()})
        self.assertEqual(r.status_code, 403)                                # cannot upload
        job = self._make_job()
        r2 = self.client.post(
            reverse("platform_admin:library_import_apply", args=[job.pk]),
            {"title": "X", "copyright_status": "unknown"})
        self.assertEqual(r2.status_code, 403)                               # cannot apply

    # --- upload validation (H5-H9 / L5-L9) ---
    def test_manage_can_upload_txt(self):
        self.client.force_login(self.platform_admin)
        r = self.client.post(self.new_url, {"source_file": _txt()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(LibraryImportJob.objects.count(), 1)
        job = LibraryImportJob.objects.first()
        self.assertEqual(job.source_format, "txt")

    def test_pdf_upload_accepted(self):
        self.client.force_login(self.platform_admin)
        r = self.client.post(self.new_url, {"source_file": _pdf_with_text()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(LibraryImportJob.objects.count(), 1)

    def test_dangerous_types_rejected(self):
        self.client.force_login(self.platform_admin)
        for name, ctype in [("x.exe", "application/octet-stream"),
                            ("x.html", "text/html"), ("x.js", "text/javascript"),
                            ("x.png", "image/png"), ("x.mp3", "audio/mpeg")]:
            self.client.post(self.new_url, {
                "source_file": SimpleUploadedFile(name, b"data", content_type=ctype)})
        self.assertEqual(LibraryImportJob.objects.count(), 0)  # none accepted

    @override_settings(LIBRARY_NOVEL_IMPORT_MAX_MB=1)
    def test_too_large_rejected(self):
        self.client.force_login(self.platform_admin)
        big = SimpleUploadedFile("big.txt", b"x" * (2 * 1024 * 1024), content_type="text/plain")
        self.client.post(self.new_url, {"source_file": big})
        self.assertEqual(LibraryImportJob.objects.count(), 0)

    def test_path_traversal_filename_is_sanitised(self):
        self.client.force_login(self.platform_admin)
        evil = SimpleUploadedFile("../../etc/passwd.txt", _TXT_BYTES, content_type="text/plain")
        r = self.client.post(self.new_url, {"source_file": evil})
        self.assertEqual(r.status_code, 302)
        job = LibraryImportJob.objects.first()
        self.assertNotIn("/", job.original_filename)
        self.assertNotIn("..", job.original_filename)

    # --- analyze / dry-run (H10-H12 / L10-L12) ---
    def test_analyze_txt_produces_counts_and_preview(self):
        self.client.force_login(self.platform_admin)
        job = self._make_job()
        self.client.post(reverse("platform_admin:library_import_analyze", args=[job.pk]))
        job.refresh_from_db()
        self.assertEqual(job.status, "analyzed")
        self.assertGreater(job.word_count, 0)
        self.assertGreaterEqual(job.chapter_count, 2)
        self.assertGreater(job.segment_count, 0)
        self.assertTrue(job.preview.get("first_segment_preview"))

    def test_analyze_creates_no_book(self):
        self.client.force_login(self.platform_admin)
        job = self._make_job()
        before = Book.objects.count()
        self.client.post(reverse("platform_admin:library_import_analyze", args=[job.pk]))
        self.assertEqual(Book.objects.count(), before)  # dry-run writes no Book

    def test_scanned_pdf_flags_needs_ocr(self):
        self.client.force_login(self.platform_admin)
        job = LibraryImportJob(status="uploaded", source_format="pdf",
                               original_filename="scan.pdf")
        job.source_file.save("scan.pdf", SimpleUploadedFile(
            "scan.pdf", _blank_pdf_bytes(), content_type="application/pdf"), save=False)
        job.save()
        self.client.post(reverse("platform_admin:library_import_analyze", args=[job.pk]))
        job.refresh_from_db()
        self.assertTrue(job.needs_ocr)
        self.assertTrue(any("OCR" in w for w in job.warnings))

    # --- apply (H13-H17 / L13-L17) ---
    def _apply(self, job, **meta):
        data = {"title": "My Novel", "copyright_status": "unknown",
                "content_language": "en", "target_cefr_level": "B1"}
        data.update(meta)
        return self.client.post(
            reverse("platform_admin:library_import_apply", args=[job.pk]), data)

    def test_apply_creates_book_chapters_segments(self):
        self.client.force_login(self.platform_admin)
        job = self._make_job(status="analyzed")
        self._apply(job)
        job.refresh_from_db()
        self.assertEqual(job.status, "imported")
        self.assertIsNotNone(job.created_book)
        self.assertGreaterEqual(job.created_book.chapters.count(), 2)
        self.assertGreater(
            NovelSegment.objects.filter(chapter__book=job.created_book).count(), 0)

    def test_imported_book_hidden_and_segments_unpublished(self):
        self.client.force_login(self.platform_admin)
        job = self._make_job(status="analyzed")
        self._apply(job)
        job.refresh_from_db()
        book = job.created_book
        self.assertFalse(book.is_published)             # hidden from students
        self.assertFalse(book.is_copyright_cleared)     # not cleared
        segs = NovelSegment.objects.filter(chapter__book=book)
        self.assertTrue(segs.exists())
        self.assertFalse(segs.filter(is_published=True).exists())  # all unpublished
        for s in segs:
            self.assertTrue(s.text_en.strip())
            self.assertEqual(s.text_ar, "")
            self.assertEqual(s.arabic_summary, "")

    def test_unknown_copyright_blocks_publishing_gate(self):
        from library.services.publishing import can_publish_book
        self.client.force_login(self.platform_admin)
        job = self._make_job(status="analyzed")
        self._apply(job)
        job.refresh_from_db()
        check = can_publish_book(job.created_book)
        self.assertFalse(check.allowed)  # unknown copyright + unpublished segments

    def test_apply_is_idempotent(self):
        self.client.force_login(self.platform_admin)
        job = self._make_job(status="analyzed")
        self._apply(job)
        job.refresh_from_db()
        first_book_id = job.created_book_id
        before = Book.objects.count()
        self._apply(job)  # second attempt
        job.refresh_from_db()
        self.assertEqual(job.created_book_id, first_book_id)  # unchanged
        self.assertEqual(Book.objects.count(), before)        # no new book

    def test_failed_import_records_clean_error(self):
        self.client.force_login(self.platform_admin)
        empty = self._make_job(upload=SimpleUploadedFile(
            "empty.txt", b"   \n  ", content_type="text/plain"), status="analyzed")
        self._apply(empty)
        empty.refresh_from_db()
        self.assertEqual(empty.status, "failed")
        self.assertTrue(empty.errors)
        self.assertIsInstance(empty.errors[0], str)
        self.assertNotIn("Traceback", empty.errors[0])  # no raw traceback leaked

    # --- admin visibility + git safety (H19, H20) ---
    def test_admin_books_list_shows_imported_hidden_book(self):
        self.client.force_login(self.platform_admin)
        job = self._make_job(status="analyzed")
        self._apply(job, title="Imported Hidden Novel")
        body = self.client.get(reverse("platform_admin:library_books")).content.decode()
        self.assertIn("Imported Hidden Novel", body)

    def test_uploaded_source_stored_under_media_not_git(self):
        job = self._make_job()
        self.assertTrue(job.source_file.name.startswith("library/imports/"))
