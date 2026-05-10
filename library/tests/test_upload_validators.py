from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from library.models import Book


def _file(name: str, content: bytes = b"x"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


class LibraryUploadValidatorTests(TestCase):
    def test_book_cover_rejects_svg(self):
        book = Book(
            title="Unsafe Cover",
            category="article",
            level="A1",
            cover=_file("cover.svg", b"<svg></svg>"),
        )

        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_book_pdf_rejects_executable(self):
        book = Book(
            title="Unsafe PDF",
            category="article",
            level="A1",
            pdf=_file("payload.exe", b"MZ"),
        )

        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_book_video_url_rejects_unrecognized_provider(self):
        book = Book(
            title="Unsafe Video",
            category="video",
            level="A1",
            video_url="https://example.com/watch/123",
        )

        with self.assertRaises(ValidationError):
            book.full_clean()
