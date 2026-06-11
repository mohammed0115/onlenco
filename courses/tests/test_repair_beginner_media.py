"""Prompt 18.2C — safe Beginner media repair (approve existing) + playback fix."""
from __future__ import annotations

import json
import re
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase

from courses.models import (
    Course, Lesson, LessonAudioScript, LessonImagePrompt,
)


def _max_playback_rate(template_name):
    p = Path(settings.BASE_DIR) / "templates" / "courses" / template_name
    txt = p.read_text(encoding="utf-8")
    rates = [float(x) for x in re.findall(r"playbackRate\s*=\s*([0-9]*\.?[0-9]+)", txt)]
    return max(rates) if rates else None


class PlaybackRateTests(TestCase):
    def test_lesson_step_playback_not_above_one(self):
        self.assertLessEqual(_max_playback_rate("lesson_step.html"), 1.0)

    def test_lesson_quiz_playback_not_above_one(self):
        self.assertLessEqual(_max_playback_rate("lesson_quiz.html"), 1.0)


class FutureTtsBeginnerSettingsTests(TestCase):
    def test_beginner_tts_uses_slow_speed_and_instruction(self):
        from courses.services.media_generation_service import (
            BEGINNER_TTS_INSTRUCTION, beginner_tts_speed, is_beginner_lesson,
        )

        class _Course:
            slug = "onlenco-beginner"

        class _Lesson:
            cefr_level = "A0"
            course = _Course()

        self.assertTrue(is_beginner_lesson(_Lesson()))
        self.assertLessEqual(beginner_tts_speed(_Lesson()), 0.9)
        self.assertIn("slowly", BEGINNER_TTS_INSTRUCTION.lower())

    def test_synthesize_speech_accepts_speed_param(self):
        import inspect
        from ai_usage.services.ai_client import synthesize_speech
        self.assertIn("speed", inspect.signature(synthesize_speech).parameters)


class RepairBeginnerMediaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")

    def _attach_audio(self, order):
        s = Lesson.objects.get(course=self.course, order=order).audio_scripts.first()
        s.generated_audio.save(f"a{order}.mp3", ContentFile(b"audio-bytes"), save=True)
        return s

    def _attach_cover(self, order):
        p = (Lesson.objects.get(course=self.course, order=order)
             .image_prompts.filter(prompt_type="cover").first())
        p.generated_image.save(f"c{order}.png", ContentFile(b"img-bytes"), save=True)
        return p

    def _repair_json(self, *args):
        out = StringIO()
        call_command("repair_beginner_media", "--format", "json", *args, stdout=out)
        return json.loads(out.getvalue())

    def test_repair_command_exists(self):
        rep = self._repair_json("--approve-existing", "--include-audio", "--include-cover-images")
        self.assertEqual(rep["canonical_lessons"], 48)
        self.assertFalse(rep["applied"])

    def test_repair_dry_run_does_not_modify_database(self):
        s = self._attach_audio(1)
        self._repair_json("--approve-existing", "--include-audio")
        s.refresh_from_db()
        self.assertNotEqual(s.generation_status, "approved")  # dry-run changed nothing

    def test_repair_approves_existing_audio_with_files_only(self):
        s = self._attach_audio(1)
        self._repair_json("--apply", "--approve-existing", "--include-audio")
        s.refresh_from_db()
        self.assertEqual(s.generation_status, "approved")
        self.assertTrue(s.is_student_visible)

    def test_repair_approves_existing_cover_images_with_files_only(self):
        p = self._attach_cover(1)
        self._repair_json("--apply", "--approve-existing", "--include-cover-images")
        p.refresh_from_db()
        self.assertEqual(p.generation_status, "approved")
        self.assertTrue(p.is_student_visible)

    def test_repair_does_not_approve_media_without_file(self):
        # An audio script WITHOUT a file must never be approved.
        no_file = Lesson.objects.get(course=self.course, order=2).audio_scripts.first()
        self._attach_audio(1)  # give one a file so apply has work to do
        self._repair_json("--apply", "--approve-existing", "--include-audio")
        no_file.refresh_from_db()
        self.assertNotEqual(no_file.generation_status, "approved")

    def test_repair_does_not_touch_noncanonical_lessons(self):
        legacy = Lesson.objects.create(
            course=self.course, title="Legacy", order=99, book_unit_number=99,
        )
        s = LessonAudioScript.objects.create(lesson=legacy, script_type="intro", script_text="hi")
        s.generated_audio.save("legacy.mp3", ContentFile(b"x"), save=True)
        self._repair_json("--apply", "--approve-existing", "--include-audio")
        s.refresh_from_db()
        self.assertNotEqual(s.generation_status, "approved")  # noncanonical untouched

    def test_repair_apply_is_idempotent(self):
        self._attach_audio(1)
        self._repair_json("--apply", "--approve-existing", "--include-audio")
        rep2 = self._repair_json("--apply", "--approve-existing", "--include-audio")
        self.assertEqual(rep2["planned_audio_approvals"], 0)

    def test_repair_does_not_regenerate_missing_illustrations(self):
        rep = self._repair_json("--apply", "--approve-existing", "--include-cover-images",
                                "--include-missing-illustrations")
        self.assertFalse(rep.get("regeneration_performed"))
        # 144 illustrations (3 per lesson × 48) remain unfilled and are plan-only.
        self.assertEqual(rep["missing_illustrations_plan_only"], 144)

    def test_audit_after_repair_reports_approved_media(self):
        self._attach_audio(1)
        self._attach_cover(1)
        self._repair_json("--apply", "--approve-existing", "--include-audio", "--include-cover-images")
        out = StringIO()
        call_command("audit_beginner_media", "--format", "json", stdout=out)
        a = json.loads(out.getvalue())
        self.assertGreaterEqual(a["audio"]["lessons_with_approved_audio"], 1)
        self.assertGreaterEqual(a["images"]["lessons_with_approved_image"], 1)
