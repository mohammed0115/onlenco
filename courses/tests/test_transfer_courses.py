"""transfer_courses: export the catalog and re-import it faithfully."""
from __future__ import annotations

import os
import tempfile

from django.core.management import call_command
from django.test import TestCase

from courses.models import (
    Course, CourseLevel, CourseUnit, Lesson, LessonAudioScript,
    LessonChecklist, LessonImagePrompt, LessonQuestion, LessonQuiz,
)


def _build_course():
    level = CourseLevel.objects.get_or_create(
        code="A1", defaults={"name": "Elementary", "order": 1})[0]
    course = Course.objects.create(
        title="Xfer", slug="xfer-a1", description="d", level=level,
        status="published", is_active=True, is_free=False, code="XFERC1")
    unit = CourseUnit.objects.create(
        course=course, code="XU1", title="U", title_ar="و", title_en="U",
        description="", description_ar="", description_en="")
    l1 = Lesson.objects.create(
        course=course, unit=unit, title="L1", content_html="<p>one</p>",
        status="published", is_active=True, order=1, code="XL1",
        access_override=Lesson.ACCESS_LOCKED)
    Lesson.objects.create(
        course=course, unit=unit, title="L2", content_html="<p>two</p>",
        status="published", is_active=True, order=2, code="XL2")
    LessonAudioScript.objects.create(
        lesson=l1, script_type="vocabulary", script_text="Hello. Hi.",
        generated_audio="lessons/audio_scripts/2026/05/x.mp3")
    LessonImagePrompt.objects.create(
        lesson=l1, prompt_type="cover", prompt="a friendly classroom",
        generated_image="lessons/image_prompts/2026/05/cover.png")
    LessonChecklist.objects.create(lesson=l1, text_en="Say hi", text_ar="قل مرحبا")
    quiz = LessonQuiz.objects.create(
        lesson=l1, code="XQ1", title="Q", title_ar="ا", title_en="Q")
    for i in range(2):
        LessonQuestion.objects.create(
            quiz=quiz, order=i, question_type="mcq",
            question_text=f"q{i}", question_text_ar="س", question_text_en=f"q{i}",
            correct_answer="a", explanation="", explanation_ar="", explanation_en="")
    return course


class TransferCoursesTests(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "courses.json")

    def test_export_then_prune_import_roundtrip(self):
        _build_course()
        call_command("transfer_courses", "--export", self.path, "--slugs", "xfer-a1")
        self.assertTrue(os.path.exists(self.path))

        # Wipe and re-import from the file (simulates a fresh production DB).
        call_command("transfer_courses", "--import", self.path, "--prune")

        self.assertEqual(Course.objects.count(), 1)
        c = Course.objects.get(slug="xfer-a1")
        self.assertFalse(c.is_free)               # scalar field preserved
        self.assertEqual(c.code, "XFERC1")
        self.assertEqual(c.level.code, "A1")
        self.assertEqual(c.lessons.count(), 2)
        self.assertEqual(CourseUnit.objects.filter(course=c).count(), 1)

        l1 = c.lessons.get(order=1)
        self.assertEqual(l1.access_override, "locked")  # admin lock survives transfer
        self.assertEqual(l1.unit.code, "XU1")           # unit re-linked by natural key
        self.assertEqual(l1.audio_scripts.count(), 1)   # audio text travels with lesson
        self.assertEqual(l1.image_prompts.count(), 1)
        # Media path references survive (bytes synced separately).
        self.assertEqual(
            l1.audio_scripts.first().generated_audio.name,
            "lessons/audio_scripts/2026/05/x.mp3")
        self.assertEqual(
            l1.image_prompts.first().generated_image.name,
            "lessons/image_prompts/2026/05/cover.png")
        self.assertEqual(l1.checklist_items.count(), 1)
        self.assertEqual(l1.quiz.questions.count(), 2)

    def test_import_without_user_or_file_fk_errors(self):
        """Export carries no User/file FKs, so import never needs them."""
        _build_course()
        call_command("transfer_courses", "--export", self.path, "--slugs", "xfer-a1")
        with open(self.path, encoding="utf-8") as fh:
            blob = fh.read()
        # No relational FK keys are serialised (substring 'teacher' still
        # appears inside values like "friendly_teacher" — check JSON keys).
        self.assertNotIn('"created_by":', blob)
        self.assertNotIn('"teacher":', blob)
        self.assertNotIn('"approved_by":', blob)
        # Re-import is clean even though no users exist for those FKs.
        call_command("transfer_courses", "--import", self.path, "--prune")
        self.assertEqual(Lesson.objects.filter(course__slug="xfer-a1").count(), 2)
