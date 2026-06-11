"""Prompt 18.2B — read-only Beginner media integrity + audio-speed audit.

The actual playback-speed FIX is deferred to 18.2C (per the prompt's "do not
apply now"); these tests verify the audit DETECTS the issues and never writes.
"""
from __future__ import annotations

import json
from io import StringIO

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase

from courses.models import (
    Course, CourseLevel, Lesson, LessonAudioScript, LessonImagePrompt,
)


class AuditBeginnerMediaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")

    def _audit_json(self, *args):
        out = StringIO()
        call_command("audit_beginner_media", "--format", "json", *args, stdout=out)
        return json.loads(out.getvalue())

    # 1
    def test_audit_command_exists_and_reports(self):
        rep = self._audit_json()
        self.assertTrue(rep["course_found"])
        self.assertEqual(rep["canonical_lessons"], 48)
        self.assertIn("images", rep)
        self.assertIn("audio", rep)
        self.assertIn("audio_speed", rep)

    # 2 — seed creates image-prompt rows WITHOUT files → missing images detected
    def test_audit_detects_missing_images(self):
        rep = self._audit_json()
        self.assertEqual(rep["images"]["lessons_with_image"], 0)
        self.assertEqual(rep["images"]["lessons_missing_image"], 48)

    # 3 — same for audio
    def test_audit_detects_missing_audio(self):
        rep = self._audit_json()
        self.assertEqual(rep["audio"]["lessons_with_audio"], 0)
        self.assertEqual(rep["audio"]["lessons_missing_audio"], 48)

    # 4 — a generated-but-unapproved file is flagged, not counted as visible
    def test_audit_detects_unapproved_media(self):
        ip = Lesson.objects.get(course=self.course, order=1).image_prompts.first()
        ip.generated_image.save("x.png", ContentFile(b"img-bytes"), save=True)
        # default generation_status is pending_generation → not student-visible
        rep = self._audit_json()
        self.assertEqual(rep["images"]["lessons_with_approved_image"], 0)
        self.assertGreaterEqual(rep["images"]["images_not_approved"], 1)

    # 5 — after the 18.2C fix the player must NOT force fast playback
    def test_audit_playback_rate_is_not_fast(self):
        rep = self._audit_json()
        mx = rep["audio_speed"]["max_playback_rate"]
        self.assertIsNotNone(mx)
        self.assertLessEqual(mx, 1.0)

    # 6 — root cause: no TTS speed setting is configured (default 1.0)
    def test_no_tts_speed_setting_configured(self):
        from django.conf import settings
        self.assertIsNone(getattr(settings, "AI_TTS_SPEED", None))

    # 7 — read-only: row counts never change
    def test_audit_does_not_modify_database(self):
        before = (
            Lesson.objects.count(),
            LessonImagePrompt.objects.count(),
            LessonAudioScript.objects.count(),
        )
        self._audit_json()
        after = (
            Lesson.objects.count(),
            LessonImagePrompt.objects.count(),
            LessonAudioScript.objects.count(),
        )
        self.assertEqual(before, after)

    # 8 — media on non-canonical lessons is reported separately
    def test_audit_reports_media_on_noncanonical_lessons(self):
        legacy = Lesson.objects.create(
            course=self.course, title="Legacy", order=99, book_unit_number=99,
        )
        LessonImagePrompt.objects.create(lesson=legacy, prompt_type="cover", prompt="x")
        rep = self._audit_json()
        self.assertEqual(rep["canonical_lessons"], 48)  # legacy excluded
        self.assertGreaterEqual(rep["noncanonical_image_rows"], 1)

    # 9 — audit scopes to the canonical 48 only
    def test_audit_uses_only_canonical_48_lessons(self):
        Lesson.objects.create(
            course=self.course, title="Extra", order=100, book_unit_number=100,
        )
        rep = self._audit_json()
        self.assertEqual(rep["canonical_lessons"], 48)

    # 10 — fail-on-critical passes on a healthy 16×3 course
    def test_fail_on_critical_passes_on_healthy_course(self):
        # Should NOT raise: structure is intact; media gaps are non-critical.
        call_command("audit_beginner_media", "--fail-on-critical", stdout=StringIO())
