"""File-upload safety: extension allowlist + size cap.

Spec rule: never accept executable uploads. Any file outside the
per-kind allowlist must raise ValidationError before it touches disk.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from courses.validators import (
    DEFAULT_MAX_BYTES, validate_audio, validate_document, validate_image,
    validate_resource_file, validate_size, validate_video,
)


def _f(name, size_bytes=1024, content=b"x"):
    """Build an UploadedFile with the requested logical size.

    We can't actually realize a 300 MB blob in memory just to test the
    size guard, so we lean on `validate_size` reading `file_obj.size`
    rather than counting content bytes.
    """
    f = SimpleUploadedFile(name, content, content_type="application/octet-stream")
    f.size = size_bytes
    return f


class ExtensionAllowlistTests(TestCase):
    def test_valid_video_extensions(self):
        for name in ["clip.mp4", "clip.webm", "clip.M4V"]:
            validate_video(_f(name))   # must not raise

    def test_invalid_video_extension(self):
        with self.assertRaises(ValidationError):
            validate_video(_f("malware.exe"))
        with self.assertRaises(ValidationError):
            validate_video(_f("bash.sh"))

    def test_valid_audio_extensions(self):
        for name in ["snd.mp3", "snd.wav", "snd.m4a", "snd.ogg"]:
            validate_audio(_f(name))

    def test_invalid_audio_extension(self):
        with self.assertRaises(ValidationError):
            validate_audio(_f("noise.exe"))

    def test_valid_image_extensions(self):
        for name in ["pic.png", "pic.jpg", "pic.JPEG", "pic.webp", "pic.gif"]:
            validate_image(_f(name))

    def test_invalid_image_extension(self):
        with self.assertRaises(ValidationError):
            validate_image(_f("pic.svg"))   # SVG can carry script

    def test_pdf_is_only_doc_type(self):
        validate_document(_f("doc.pdf"))
        with self.assertRaises(ValidationError):
            validate_document(_f("doc.docx"))


class SizeCapTests(TestCase):
    def test_size_under_cap_passes(self):
        validate_size(_f("ok.mp4", size_bytes=1024))

    def test_size_over_default_cap_rejected(self):
        with self.assertRaises(ValidationError):
            validate_size(_f("huge.mp4", size_bytes=DEFAULT_MAX_BYTES + 1))

    def test_video_over_cap_rejected(self):
        with self.assertRaises(ValidationError):
            validate_video(_f("huge.mp4", size_bytes=DEFAULT_MAX_BYTES + 1))


class ResourceDispatchTests(TestCase):
    def test_pdf_resource_routes_to_document(self):
        validate_resource_file(_f("a.pdf"), "pdf")
        with self.assertRaises(ValidationError):
            validate_resource_file(_f("a.exe"), "pdf")

    def test_video_resource(self):
        validate_resource_file(_f("a.mp4"), "video")
        with self.assertRaises(ValidationError):
            validate_resource_file(_f("a.mov"), "video")

    def test_worksheet_accepts_pdf_or_docx(self):
        validate_resource_file(_f("a.pdf"), "worksheet")
        validate_resource_file(_f("a.docx"), "worksheet")
        with self.assertRaises(ValidationError):
            validate_resource_file(_f("a.exe"), "worksheet")

    def test_link_resource_skipped(self):
        # `link` resources don't carry a file — should silently no-op
        # even if you pass one.
        validate_resource_file(_f("anything.exe"), "link")
