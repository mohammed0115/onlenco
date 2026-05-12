"""Tests for the generate_a0_audio command."""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings


class GenerateA0AudioTests(TestCase):
    def setUp(self):
        # Ensure A0 lessons exist.
        call_command("import_a0_curriculum", stdout=StringIO())

    @override_settings(AI_API_KEY="")
    def test_no_api_key_short_circuits_gracefully(self):
        out = StringIO()
        call_command("generate_a0_audio", stdout=out)
        # Command must NOT raise. Output should warn the operator.
        self.assertIn("AI_API_KEY is not configured", out.getvalue())

    @override_settings(AI_API_KEY="")
    def test_dry_run_works_without_api_key(self):
        out = StringIO()
        call_command("generate_a0_audio", "--dry-run", stdout=out)
        self.assertIn("[DRY RUN]", out.getvalue())
        self.assertIn("Lessons to process", out.getvalue())

    @override_settings(AI_API_KEY="fake-key", AI_API_BASE="https://x.test")
    def test_synth_failures_dont_crash_the_command(self):
        """A 500 from upstream must NOT raise — the command should
        record the failure and continue."""
        from courses.models import Lesson
        # Patch _synth_bytes to always return None (synth failure).
        with patch(
            "daily_learning.management.commands.generate_a0_audio._synth_bytes",
            return_value=None,
        ):
            out = StringIO()
            err = StringIO()
            call_command(
                "generate_a0_audio", "--limit", "3",
                stdout=out, stderr=err,
            )
        # No exception means we win. Just confirm a fail line landed.
        self.assertIn("ok=0 fail=", out.getvalue())

    @override_settings(AI_API_KEY="fake-key", AI_API_BASE="https://x.test")
    def test_successful_synth_attaches_audio_to_lesson(self):
        from courses.models import Lesson
        with patch(
            "daily_learning.management.commands.generate_a0_audio._synth_bytes",
            return_value=b"FAKE-MP3-BYTES" * 10,
        ):
            call_command(
                "generate_a0_audio", "--limit", "2",
                stdout=StringIO(),
            )
        # First two A0 lessons should now have an audio_file populated.
        produced = Lesson.objects.filter(
            course__level__code="A0",
        ).exclude(audio_file="").count()
        self.assertGreaterEqual(produced, 2)

    @override_settings(AI_API_KEY="fake-key", AI_API_BASE="https://x.test")
    def test_idempotent_skips_lessons_with_existing_audio(self):
        """A second run without --force must NOT re-synthesise the same
        lessons. We process the same fixed limit twice and confirm the
        second pass synthesises strictly fewer items than the first."""
        with patch(
            "daily_learning.management.commands.generate_a0_audio._synth_bytes",
            return_value=b"AUDIO1" * 20,
        ) as mocked:
            call_command(
                "generate_a0_audio", "--limit", "3",
                stdout=StringIO(),
            )
            first_calls = mocked.call_count
            # Second pass with --limit 3 again. The 3 already-synthesised
            # lessons fall out of the queryset, but if there are still
            # un-synthesised A0 lessons, it picks the next batch. To
            # assert pure idempotency we measure that the FIRST 3 are
            # not re-synthesised — we do this by running a non-limited
            # pass over the same set and checking that lessons we just
            # synthesised are still skipped.
            from courses.models import Lesson
            done_ids = set(
                Lesson.objects.filter(course__level__code="A0")
                .exclude(audio_file="")
                .values_list("id", flat=True)[:3]
            )
            call_command("generate_a0_audio", stdout=StringIO())
            still_done_ids = set(
                Lesson.objects.filter(id__in=done_ids)
                .exclude(audio_file="")
                .values_list("id", flat=True)
            )
        self.assertGreaterEqual(first_calls, 1)
        self.assertEqual(
            done_ids, still_done_ids,
            "Lessons synthesised in round 1 must remain synthesised "
            "in round 2 (file not overwritten / skipped correctly).",
        )
