"""approve_generated_media: bulk-approve only generated media that has a file."""
from __future__ import annotations

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase

from courses.models import (
    Course, CourseLevel, Lesson, LessonAudioScript, LessonImagePrompt,
)


def _course(slug="elem", code="A1"):
    level = CourseLevel.objects.get_or_create(code=code, defaults={"name": code, "order": 1})[0]
    return Course.objects.create(
        title="C", slug=slug, level=level, status="published", is_active=True, is_free=True)


class ApproveGeneratedMediaTests(TestCase):
    def setUp(self):
        self.course = _course()
        self.lesson = Lesson.objects.create(
            course=self.course, title="L1", content_html="<p>x</p>",
            status="published", is_active=True, order=1, code="AML1")
        # An image WITH a file, awaiting review.
        self.img = LessonImagePrompt.objects.create(
            lesson=self.lesson, prompt_type="cover", prompt="p",
            generation_status="needs_review")
        self.img.generated_image.save("c.png", ContentFile(b"img"), save=True)
        # An image prompt with NO file (should stay untouched).
        self.empty = LessonImagePrompt.objects.create(
            lesson=self.lesson, prompt_type="vocabulary", prompt="p2",
            generation_status="needs_review")
        # An audio script WITH a file, awaiting review.
        self.aud = LessonAudioScript.objects.create(
            lesson=self.lesson, script_type="intro", script_text="hi",
            generation_status="needs_review")
        self.aud.generated_audio.save("a.mp3", ContentFile(b"aud"), save=True)

    def test_dry_run_changes_nothing(self):
        call_command("approve_generated_media", "--course", "elem", "--media", "all")
        self.img.refresh_from_db()
        self.assertEqual(self.img.generation_status, "needs_review")

    def test_confirm_approves_only_media_with_files(self):
        call_command("approve_generated_media", "--course", "elem", "--media", "all", "--confirm")
        self.img.refresh_from_db()
        self.empty.refresh_from_db()
        self.aud.refresh_from_db()
        self.assertEqual(self.img.generation_status, "approved")
        self.assertTrue(self.img.is_student_visible)
        self.assertEqual(self.aud.generation_status, "approved")
        self.assertTrue(self.aud.is_student_visible)
        # No file → must NOT be approved (keeps the clean placeholder).
        self.assertEqual(self.empty.generation_status, "needs_review")

    def test_media_images_only(self):
        call_command("approve_generated_media", "--course", "elem", "--media", "images", "--confirm")
        self.img.refresh_from_db()
        self.aud.refresh_from_db()
        self.assertEqual(self.img.generation_status, "approved")
        self.assertEqual(self.aud.generation_status, "needs_review")  # audio untouched
