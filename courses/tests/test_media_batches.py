"""Coverage for P07 / P08 / P13 — image and audio batch commands.

All API calls are mocked. We verify:
  - The commands accept the documented selection flags.
  - Dry-run prints a plan and writes nothing.
  - The text cleaner strips HTML / underscores / placeholders.
  - On success the model row is marked is_generated=True and the
    generated_* field carries non-empty bytes.
  - Re-running without --regenerate skips already-generated rows
    (idempotency).
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from courses.models import (
    Course, Lesson, LessonAudioScript, LessonImagePrompt,
)
from courses.services.onlenco_media_clients import (
    GenerationResult, clean_script_for_tts,
)


COURSE_SLUG = "onlenco-beginner"


class TextCleanerTests(TestCase):
    def test_strips_html_tags(self):
        out = clean_script_for_tts("<h3>Lesson Goal</h3><p>Say hello.</p>")
        self.assertNotIn("<", out)
        self.assertNotIn(">", out)
        self.assertIn("Lesson Goal", out)
        self.assertIn("Say hello", out)

    def test_underscores_become_blank(self):
        out = clean_script_for_tts("Fill the ____ now.")
        self.assertIn("blank", out)
        self.assertNotIn("____", out)

    def test_placeholders_removed(self):
        out = clean_script_for_tts("Say hello (populated in P12) please.")
        self.assertNotIn("populated", out)
        self.assertNotIn("(populated", out)

    def test_whitespace_collapsed(self):
        out = clean_script_for_tts("Say   hello.\n\n   World.")
        self.assertNotIn("  ", out)


class ImageBatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet", stdout=StringIO())

    def test_dry_run_writes_nothing(self):
        out = StringIO()
        with patch("courses.management.commands.onlenco_beginner_image_batch.generate_image") as m:
            call_command(
                "onlenco_beginner_image_batch",
                "--dry-run", stdout=out,
            )
            self.assertFalse(m.called, "DRY RUN must not call the API")
        self.assertIn("DRY RUN", out.getvalue())

    def test_unit_flag_scopes_to_one_lesson(self):
        out = StringIO()
        with patch(
            "courses.management.commands.onlenco_beginner_image_batch.generate_image"
        ) as m:
            m.return_value = GenerationResult(ok=True, bytes_=b"\x89PNG\r\n", cost_estimate_usd=0.04)
            call_command(
                "onlenco_beginner_image_batch",
                "--unit", "1", "--prompt-type", "cover",
                stdout=out,
            )
            self.assertEqual(m.call_count, 1)

        # Confirm the LessonImagePrompt row is now marked generated.
        lesson_1 = Lesson.objects.get(course__slug=COURSE_SLUG, order=1)
        cover = LessonImagePrompt.objects.get(lesson=lesson_1, prompt_type="cover")
        self.assertTrue(cover.is_generated)
        self.assertTrue(cover.generated_image)

    def test_already_generated_rows_skipped_without_regenerate(self):
        # Pre-mark unit 2's cover as generated.
        l2 = Lesson.objects.get(course__slug=COURSE_SLUG, order=2)
        LessonImagePrompt.objects.filter(lesson=l2, prompt_type="cover").update(
            is_generated=True,
        )
        out = StringIO()
        with patch(
            "courses.management.commands.onlenco_beginner_image_batch.generate_image"
        ) as m:
            m.return_value = GenerationResult(ok=True, bytes_=b"\x89PNG", cost_estimate_usd=0.04)
            call_command(
                "onlenco_beginner_image_batch",
                "--unit", "2", "--prompt-type", "cover",
                stdout=out,
            )
            # Since the only matching row is already generated, no call.
            self.assertEqual(m.call_count, 0)

    def test_failed_call_does_not_mark_generated(self):
        out = StringIO()
        with patch(
            "courses.management.commands.onlenco_beginner_image_batch.generate_image"
        ) as m:
            m.return_value = GenerationResult(ok=False, error="quota_exceeded")
            call_command(
                "onlenco_beginner_image_batch",
                "--unit", "3", "--prompt-type", "cover",
                stdout=out,
            )
        l3 = Lesson.objects.get(course__slug=COURSE_SLUG, order=3)
        cover = LessonImagePrompt.objects.get(lesson=l3, prompt_type="cover")
        self.assertFalse(cover.is_generated)


class AudioBatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet", stdout=StringIO())

    def test_dry_run_writes_nothing(self):
        out = StringIO()
        with patch("courses.management.commands.onlenco_beginner_audio_batch.generate_audio") as m:
            call_command(
                "onlenco_beginner_audio_batch",
                "--dry-run", stdout=out,
            )
            self.assertFalse(m.called)
        self.assertIn("DRY RUN", out.getvalue())

    def test_unit_flag_persists_audio_bytes(self):
        out = StringIO()
        with patch(
            "courses.management.commands.onlenco_beginner_audio_batch.generate_audio"
        ) as m:
            m.return_value = GenerationResult(ok=True, bytes_=b"ID3\x03\x00\x00", cost_estimate_usd=0.001)
            call_command(
                "onlenco_beginner_audio_batch",
                "--unit", "1", "--script-type", "intro",
                stdout=out,
            )
            self.assertEqual(m.call_count, 1)

        l1 = Lesson.objects.get(course__slug=COURSE_SLUG, order=1)
        intro = LessonAudioScript.objects.get(lesson=l1, script_type="intro")
        self.assertTrue(intro.is_generated)
        self.assertTrue(intro.generated_audio)

    def test_text_is_cleaned_before_tts(self):
        """The TTS call should receive cleaned text, never raw HTML."""
        # Pre-load an HTML-rich script onto unit 1's vocabulary slot.
        l1 = Lesson.objects.get(course__slug=COURSE_SLUG, order=1)
        vocab = LessonAudioScript.objects.get(lesson=l1, script_type="vocabulary")
        vocab.script_text = "<h3>Vocab</h3><p>Hello and ____ goodbye.</p>"
        vocab.is_generated = False
        vocab.save()

        out = StringIO()
        with patch(
            "courses.management.commands.onlenco_beginner_audio_batch.generate_audio"
        ) as m:
            m.return_value = GenerationResult(ok=True, bytes_=b"ID3", cost_estimate_usd=0.001)
            call_command(
                "onlenco_beginner_audio_batch",
                "--unit", "1", "--script-type", "vocabulary",
                stdout=out,
            )
            self.assertEqual(m.call_count, 1)
            sent_text = m.call_args.args[0]
            self.assertNotIn("<h3>", sent_text)
            self.assertNotIn("____", sent_text)
            self.assertIn("Hello", sent_text)


class FullMediaWrapperTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet", stdout=StringIO())

    def test_dry_run_calls_both_sub_commands(self):
        out = StringIO()
        # Both sub-commands should hit their --dry-run paths and not call APIs.
        with (
            patch("courses.management.commands.onlenco_beginner_image_batch.generate_image") as mi,
            patch("courses.management.commands.onlenco_beginner_audio_batch.generate_audio") as ma,
        ):
            call_command("onlenco_beginner_full_media", "--dry-run", stdout=out)
            self.assertFalse(mi.called)
            self.assertFalse(ma.called)
        body = out.getvalue()
        self.assertIn("Image batch", body)
        self.assertIn("Audio batch", body)
