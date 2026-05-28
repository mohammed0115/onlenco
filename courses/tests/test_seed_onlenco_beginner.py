"""Coverage for the Onlenco Beginner 48-unit seed command.

Verifies the seed runs, builds all required rows, and is idempotent —
running it a second time must not duplicate any row.
"""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from courses.models import (
    Course, CourseUnit, Lesson, LessonAudioScript, LessonChecklist,
    LessonImagePrompt, LessonQuiz,
)


COURSE_SLUG = "onlenco-beginner"


class OnlencoBeginnerSeedTests(TestCase):
    def _run_seed(self):
        out = StringIO()
        call_command("seed_onlenco_beginner_48_units", "--quiet", stdout=out)
        return out.getvalue()

    def test_seed_onlenco_beginner_48_units_runs(self):
        out = self._run_seed()
        self.assertIn("seed complete", out.lower())

    def test_course_created(self):
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        self.assertEqual(course.title, "Onlenco Beginner English Foundation")
        self.assertTrue(course.is_active)
        self.assertEqual(course.status, "published")

    def test_course_has_48_learning_units(self):
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        self.assertEqual(
            Lesson.objects.filter(course=course).count(), 48,
            "expected 48 Lessons (one per Learning Unit)",
        )
        # CourseUnits: 48 lessons ÷ 3 lessons per unit = 16 unit groups.
        self.assertEqual(
            CourseUnit.objects.filter(course=course).count(), 16,
            "expected 16 CourseUnits grouping the 48 Lessons",
        )

    def test_each_unit_has_content_html_and_content_ar(self):
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        for lesson in Lesson.objects.filter(course=course):
            self.assertTrue(
                lesson.content_html.strip(),
                f"Lesson {lesson.order} has empty content_html",
            )
            self.assertTrue(
                lesson.content_ar.strip(),
                f"Lesson {lesson.order} has empty content_ar",
            )
            # Sanity: the 12 required English sections all appear.
            for marker in [
                "Lesson Goal", "New Language", "Key Vocabulary",
                "Grammar Focus", "Visual Guide", "Examples",
                "Mini Dialogue", "Practice Activity", "Listening Task",
                "Speaking Practice", "AI Tutor Drill", "Checklist",
            ]:
                self.assertIn(
                    marker, lesson.content_html,
                    f"Lesson {lesson.order} missing section: {marker}",
                )
            # Arabic block: at least the goal + grammar headings present.
            self.assertIn("هدف الدرس", lesson.content_ar)
            self.assertIn("ملاحظة للطالب العربي", lesson.content_ar)

    def test_each_unit_has_checklist(self):
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        for lesson in Lesson.objects.filter(course=course):
            n = LessonChecklist.objects.filter(lesson=lesson).count()
            self.assertGreaterEqual(
                n, 1,
                f"Lesson {lesson.order} ({lesson.title}) has no checklist",
            )

    def test_each_unit_has_image_prompts(self):
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        for lesson in Lesson.objects.filter(course=course):
            prompts = LessonImagePrompt.objects.filter(lesson=lesson)
            self.assertEqual(
                prompts.count(), 4,
                f"Lesson {lesson.order} should have 4 image prompts",
            )
            kinds = set(prompts.values_list("prompt_type", flat=True))
            self.assertEqual(
                kinds, {"cover", "vocabulary", "grammar", "quiz"},
                f"Lesson {lesson.order} image prompt types: {kinds}",
            )

    def test_each_unit_has_audio_scripts(self):
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        for lesson in Lesson.objects.filter(course=course):
            scripts = LessonAudioScript.objects.filter(lesson=lesson)
            self.assertEqual(
                scripts.count(), 6,
                f"Lesson {lesson.order} should have 6 audio scripts",
            )
            kinds = set(scripts.values_list("script_type", flat=True))
            self.assertEqual(
                kinds,
                {"intro", "vocabulary", "examples", "dialogue", "listening", "speaking"},
                f"Lesson {lesson.order} audio script types: {kinds}",
            )
            # All audio is American per the spec.
            for s in scripts:
                self.assertEqual(s.accent, "american")
                self.assertFalse(s.is_generated)

    def test_each_unit_has_ai_tutor_drill(self):
        """The lesson's content_html must include an AI Tutor Drill section."""
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        for lesson in Lesson.objects.filter(course=course):
            self.assertIn(
                "AI Tutor Drill", lesson.content_html,
                f"Lesson {lesson.order} missing AI Tutor Drill section",
            )

    def test_content_is_original_not_copied(self):
        """No DK / EFE character names leak into seeded content.

        These names (full list in METHOD_SPEC §7) must never appear in our
        seeded text — they would indicate accidental copying from the
        reference book. Uses word-boundary matching so legitimate Onlenco
        names like "Amani" don't trigger on the "Aman" substring.
        """
        import re
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        forbidden = ["Lyla", "Pablo", "Mary", "Sarah", "Dan", "Harry",
                     "Bruno", "Aman", "Leesa", "Una", "Robbie", "Ginger",
                     "Lizzie", "Felix", "Coco", "Milo"]
        # Word-boundary patterns — match standalone names only.
        patterns = {n: re.compile(rf"\b{re.escape(n)}\b") for n in forbidden}
        for lesson in Lesson.objects.filter(course=course):
            for blob in (lesson.content_html, lesson.content_ar):
                for name, pat in patterns.items():
                    self.assertIsNone(
                        pat.search(blob),
                        f"Forbidden EFE name {name!r} found in lesson "
                        f"{lesson.order} ({lesson.title})",
                    )

    def test_seed_is_idempotent(self):
        """Running the seed twice must not duplicate any row."""
        self._run_seed()
        course = Course.objects.get(slug=COURSE_SLUG)
        before = {
            "courses":     Course.objects.filter(slug=COURSE_SLUG).count(),
            "course_units": CourseUnit.objects.filter(course=course).count(),
            "lessons":     Lesson.objects.filter(course=course).count(),
            "checklist":   LessonChecklist.objects.filter(lesson__course=course).count(),
            "img_prompts": LessonImagePrompt.objects.filter(lesson__course=course).count(),
            "audio_scripts": LessonAudioScript.objects.filter(lesson__course=course).count(),
            "quizzes":     LessonQuiz.objects.filter(lesson__course=course).count(),
        }

        # Re-run with a fresh stream.
        self._run_seed()

        after = {
            "courses":     Course.objects.filter(slug=COURSE_SLUG).count(),
            "course_units": CourseUnit.objects.filter(course=course).count(),
            "lessons":     Lesson.objects.filter(course=course).count(),
            "checklist":   LessonChecklist.objects.filter(lesson__course=course).count(),
            "img_prompts": LessonImagePrompt.objects.filter(lesson__course=course).count(),
            "audio_scripts": LessonAudioScript.objects.filter(lesson__course=course).count(),
            "quizzes":     LessonQuiz.objects.filter(lesson__course=course).count(),
        }

        self.assertEqual(before, after, "Seed is not idempotent — counts changed on second run")
        # Specific guarantees:
        self.assertEqual(after["courses"], 1)
        self.assertEqual(after["lessons"], 48)
        self.assertEqual(after["course_units"], 16)
        self.assertEqual(after["quizzes"], 48)
