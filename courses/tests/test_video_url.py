"""Lesson video: upload-or-URL with provider detection + fallback.

Spec:
- Accept upload (.mp4/.webm/.m4v) OR URL.
- URL must be YouTube, Vimeo, or a direct video file.
- Player order: uploaded file first; fall back to URL if the file is missing.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase

from courses.models import Course, CourseLevel, Lesson
from courses.validators import parse_video_url, validate_video_url


class ParseVideoUrlTests(TestCase):
    def test_youtube_watch(self):
        out = parse_video_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(out["kind"], "youtube")
        self.assertEqual(out["id"], "dQw4w9WgXcQ")
        self.assertEqual(out["embed_url"], "https://www.youtube.com/embed/dQw4w9WgXcQ")

    def test_youtu_be_short(self):
        out = parse_video_url("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(out["kind"], "youtube")
        self.assertEqual(out["id"], "dQw4w9WgXcQ")

    def test_youtube_embed(self):
        out = parse_video_url("https://www.youtube.com/embed/dQw4w9WgXcQ")
        self.assertEqual(out["kind"], "youtube")

    def test_youtube_shorts(self):
        out = parse_video_url("https://www.youtube.com/shorts/abcDEF12345")
        self.assertEqual(out["kind"], "youtube")
        self.assertEqual(out["id"], "abcDEF12345")

    def test_vimeo_canonical(self):
        out = parse_video_url("https://vimeo.com/123456789")
        self.assertEqual(out["kind"], "vimeo")
        self.assertEqual(out["id"], "123456789")
        self.assertEqual(out["embed_url"], "https://player.vimeo.com/video/123456789")

    def test_vimeo_player(self):
        out = parse_video_url("https://player.vimeo.com/video/123456789")
        self.assertEqual(out["kind"], "vimeo")

    def test_direct_mp4(self):
        out = parse_video_url("https://cdn.example.com/lesson.mp4")
        self.assertEqual(out["kind"], "direct")
        self.assertEqual(out["embed_url"], "https://cdn.example.com/lesson.mp4")

    def test_direct_webm(self):
        out = parse_video_url("https://cdn.example.com/lesson.webm?x=1")
        self.assertEqual(out["kind"], "direct")

    def test_unrecognised_returns_none(self):
        self.assertIsNone(parse_video_url("https://dailymotion.com/x123"))
        self.assertIsNone(parse_video_url("https://example.com/some-page"))
        self.assertIsNone(parse_video_url(""))


class ValidateVideoUrlTests(TestCase):
    def test_accepts_youtube(self):
        validate_video_url("https://youtu.be/dQw4w9WgXcQ")

    def test_accepts_vimeo(self):
        validate_video_url("https://vimeo.com/123456789")

    def test_accepts_direct(self):
        validate_video_url("https://cdn.example.com/lesson.mp4")

    def test_rejects_dailymotion(self):
        with self.assertRaises(ValidationError):
            validate_video_url("https://www.dailymotion.com/video/abc")

    def test_rejects_random_url(self):
        with self.assertRaises(ValidationError):
            validate_video_url("https://example.com/page")

    def test_blank_is_ok(self):
        validate_video_url("")  # blank URLField is allowed


class LessonCleanTests(TestCase):
    def setUp(self):
        self.level = CourseLevel.objects.create(code="A1", name="A1")
        self.course = Course.objects.create(title="C", slug="vc", level=self.level)

    def test_invalid_video_url_raises_on_clean(self):
        l = Lesson(course=self.course, title="L", video_url="https://example.com/x")
        with self.assertRaises(ValidationError):
            l.full_clean()

    def test_valid_video_url_passes_clean(self):
        l = Lesson(course=self.course, title="L",
                   video_url="https://youtu.be/dQw4w9WgXcQ")
        l.full_clean()  # must not raise


class LessonEmbedResolverTests(TestCase):
    def setUp(self):
        self.level = CourseLevel.objects.create(code="A1", name="A1")
        self.course = Course.objects.create(title="C", slug="vc2", level=self.level)

    def test_youtube_url_resolves_to_youtube_embed(self):
        l = Lesson.objects.create(
            course=self.course, title="L",
            video_url="https://youtu.be/dQw4w9WgXcQ",
        )
        embed = l.get_video_embed()
        self.assertEqual(embed["kind"], "youtube")
        self.assertEqual(embed["embed_url"], "https://www.youtube.com/embed/dQw4w9WgXcQ")

    def test_vimeo_url_resolves(self):
        l = Lesson.objects.create(
            course=self.course, title="L",
            video_url="https://vimeo.com/123456789",
        )
        embed = l.get_video_embed()
        self.assertEqual(embed["kind"], "vimeo")
        self.assertEqual(embed["embed_url"], "https://player.vimeo.com/video/123456789")

    def test_direct_url_resolves(self):
        l = Lesson.objects.create(
            course=self.course, title="L",
            video_url="https://cdn.example.com/x.mp4",
        )
        embed = l.get_video_embed()
        self.assertEqual(embed["kind"], "direct")
        self.assertEqual(embed["url"], "https://cdn.example.com/x.mp4")

    def test_no_video_returns_none(self):
        l = Lesson.objects.create(course=self.course, title="L")
        self.assertIsNone(l.get_video_embed())

    def test_unrecognised_url_returns_none(self):
        l = Lesson.objects.create(
            course=self.course, title="L",
            # bypass clean() so we can test the resolver's defensive path
        )
        l.video_url = "https://dailymotion.com/x"
        self.assertIsNone(l.get_video_embed())
