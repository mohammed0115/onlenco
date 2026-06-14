"""Optional video step — appears (before finish) only when the lesson has video."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from courses.models import Course, CourseLevel, Lesson
from courses.views import lesson_step_kinds


User = get_user_model()


class LessonStepKindsTests(TestCase):
    def setUp(self):
        level = CourseLevel.objects.get_or_create(code="A1", defaults={"name": "E", "order": 1})[0]
        self.course = Course.objects.create(
            title="C", slug="vid-c", level=level, status="published",
            is_active=True, is_free=True)
        self.lesson = Lesson.objects.create(
            course=self.course, title="L1", content_html="<p>x</p>",
            status="published", is_active=True, order=1, code="VIDL1")

    def test_no_video_no_video_step(self):
        kinds = lesson_step_kinds(self.lesson)
        self.assertNotIn("video", kinds)
        self.assertEqual(kinds[-1], "finish")
        self.assertEqual(len(kinds), 7)

    def test_video_step_inserted_before_finish(self):
        self.lesson.video_url = "https://www.youtube.com/watch?v=abc123"
        self.lesson.save(update_fields=["video_url"])
        kinds = lesson_step_kinds(self.lesson)
        self.assertIn("video", kinds)
        self.assertEqual(len(kinds), 8)
        # video sits immediately before finish
        self.assertEqual(kinds[kinds.index("video") + 1], "finish")


class VideoStepRenderTests(TestCase):
    """End-to-end on the seeded beginner course (lesson 1 is always openable)."""

    @classmethod
    def setUpTestData(cls):
        from courses.models import CourseEnrollment
        from courses.tests.test_super_lesson_01 import (
            _get_lesson_quiz, _make_student, _seed_all,
        )
        _seed_all()
        cls.course, cls.lesson, _ = _get_lesson_quiz()
        cls.student = _make_student("vid-student")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)

    def _login(self):
        from courses.tests.test_super_lesson_01 import _login
        return _login(self.student)

    def test_video_step_404_without_video(self):
        url = reverse("courses:lesson_step", args=[self.course.pk, self.lesson.pk, "video"])
        self.assertEqual(self._login().get(url, HTTP_HOST="127.0.0.1").status_code, 404)

    def test_video_card_and_step_render_with_video(self):
        self.lesson.video_url = "https://www.youtube.com/watch?v=abc123"
        self.lesson.save(update_fields=["video_url"])
        client = self._login()

        # Detail page shows a video card linking to the video step.
        detail = client.get(
            reverse("courses:lesson_detail", args=[self.course.pk, self.lesson.pk]),
            HTTP_HOST="127.0.0.1").content.decode()
        self.assertIn("/step/video/", detail)

        # The video step renders an embed player.
        step = client.get(
            reverse("courses:lesson_step", args=[self.course.pk, self.lesson.pk, "video"]),
            HTTP_HOST="127.0.0.1")
        self.assertEqual(step.status_code, 200)
        self.assertIn("youtube.com/embed/abc123", step.content.decode())

    def test_uploaded_file_renders_video_tag(self):
        from django.core.files.base import ContentFile
        self.lesson.video_file.save("v.mp4", ContentFile(b"\x00\x00mp4"), save=True)
        step = self._login().get(
            reverse("courses:lesson_step", args=[self.course.pk, self.lesson.pk, "video"]),
            HTTP_HOST="127.0.0.1").content.decode()
        self.assertIn("onlenco-video__el", step)
