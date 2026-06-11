"""Prompt 18.2D — generate ONLY missing Beginner illustration images (mocked)."""
from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase

from courses.models import Course, Lesson, LessonAudioScript, LessonImagePrompt

_FAKE_PNG = b"\x89PNG\r\n\x1a\n-fake-image-bytes"
_GEN = "courses.services.media_generation_service.ai_client.generate_image"


class GenerateMissingIllustrationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")

    def _cmd_json(self, *args):
        out = StringIO()
        call_command("generate_missing_beginner_illustrations", "--format", "json",
                     *args, stdout=out)
        return json.loads(out.getvalue())

    def _rows_with_file(self, **flt):
        return LessonImagePrompt.objects.filter(
            lesson__course=self.course, **flt
        ).exclude(generated_image="").count()

    # 1
    def test_command_exists(self):
        rep = self._cmd_json()
        self.assertEqual(rep["canonical_lessons"], 48)
        self.assertFalse(rep["applied"])
        self.assertEqual(rep["types"], ["vocabulary", "grammar", "quiz"])

    # 2
    def test_dry_run_does_not_generate_or_modify_db(self):
        before = self._rows_with_file()
        with patch(_GEN, return_value=_FAKE_PNG) as m:
            self._cmd_json("--limit", "5")  # dry-run default
        m.assert_not_called()
        self.assertEqual(self._rows_with_file(), before)

    # 3
    def test_generates_only_vocab_grammar_quiz(self):
        with patch(_GEN, return_value=_FAKE_PNG):
            self._cmd_json("--apply", "--limit", "12")
        # No cover image was generated.
        self.assertEqual(self._rows_with_file(prompt_type="cover"), 0)
        self.assertEqual(self._rows_with_file(), 12)

    # 4
    def test_does_not_regenerate_cover_images(self):
        cover = (Lesson.objects.get(course=self.course, order=1)
                 .image_prompts.filter(prompt_type="cover").first())
        cover.generated_image.save("cover.png", ContentFile(b"existing"), save=True)
        cover.generation_status = "approved"
        cover.save(update_fields=["generation_status"])
        with patch(_GEN, return_value=_FAKE_PNG):
            self._cmd_json("--apply", "--limit", "12")
        cover.refresh_from_db()
        self.assertEqual(cover.generated_image.read(), b"existing")  # untouched

    # 5
    def test_does_not_touch_existing_approved_illustrations(self):
        voc = (Lesson.objects.get(course=self.course, order=1)
               .image_prompts.filter(prompt_type="vocabulary").first())
        voc.generated_image.save("voc.png", ContentFile(b"approved-voc"), save=True)
        voc.generation_status = "approved"
        voc.save(update_fields=["generation_status"])
        with patch(_GEN, return_value=_FAKE_PNG):
            self._cmd_json("--apply", "--limit", "12")
        voc.refresh_from_db()
        self.assertEqual(voc.generation_status, "approved")
        self.assertEqual(voc.generated_image.read(), b"approved-voc")

    # 6
    def test_does_not_touch_audio(self):
        before = LessonAudioScript.objects.filter(
            lesson__course=self.course).exclude(generated_audio="").count()
        with patch(_GEN, return_value=_FAKE_PNG):
            self._cmd_json("--apply", "--limit", "12")
        after = LessonAudioScript.objects.filter(
            lesson__course=self.course).exclude(generated_audio="").count()
        self.assertEqual(before, after)

    # 7
    def test_does_not_touch_noncanonical_lessons(self):
        legacy = Lesson.objects.create(
            course=self.course, title="Legacy", order=99, book_unit_number=99)
        p = LessonImagePrompt.objects.create(
            lesson=legacy, prompt_type="vocabulary", prompt="x")
        with patch(_GEN, return_value=_FAKE_PNG):
            self._cmd_json("--apply", "--limit", "12")
        p.refresh_from_db()
        self.assertFalse(bool(p.generated_image))  # never generated

    # 8
    def test_limit_option_limits_batch(self):
        with patch(_GEN, return_value=_FAKE_PNG):
            rep = self._cmd_json("--apply", "--limit", "3")
        self.assertEqual(rep["planned_generation_count"], 3)
        self.assertEqual(rep["generated_count"], 3)
        self.assertEqual(self._rows_with_file(), 3)

    # 9
    def test_book_unit_filter(self):
        with patch(_GEN, return_value=_FAKE_PNG):
            rep = self._cmd_json("--apply", "--book-unit", "5", "--limit", "12")
        self.assertEqual(rep["affected_book_units"], [5])
        # Only book unit 5 illustrations got files.
        other = LessonImagePrompt.objects.filter(
            lesson__course=self.course).exclude(
            lesson__book_unit_number=5).exclude(generated_image="").count()
        self.assertEqual(other, 0)

    # 10
    def test_generated_images_not_student_visible(self):
        with patch(_GEN, return_value=_FAKE_PNG):
            self._cmd_json("--apply", "--limit", "3")
        for p in LessonImagePrompt.objects.filter(
                lesson__course=self.course).exclude(generated_image=""):
            self.assertEqual(p.generation_status, "needs_review")
            self.assertFalse(p.is_student_visible)

    # 11
    def test_generation_is_idempotent_after_success(self):
        with patch(_GEN, return_value=_FAKE_PNG):
            self._cmd_json("--apply", "--book-unit", "5", "--limit", "12")
            rep2 = self._cmd_json("--apply", "--book-unit", "5", "--limit", "12")
        self.assertEqual(rep2["planned_generation_count"], 0)
        self.assertEqual(rep2["generated_count"], 0)

    # 12
    def test_audit_after_generation_reports_fewer_missing(self):
        def _missing():
            out = StringIO()
            call_command("audit_beginner_media", "--format", "json", stdout=out)
            return json.loads(out.getvalue())["images"]["image_rows_missing_file"]
        before = _missing()
        with patch(_GEN, return_value=_FAKE_PNG):
            self._cmd_json("--apply", "--limit", "10")
        self.assertEqual(_missing(), before - 10)

    # 14 — grammar quality guard (Prompt 18.2F-Batch-Next)
    def test_grammar_guard_only_augments_grammar_prompts(self):
        from courses.services.media_generation_service import effective_image_prompt
        les = Lesson.objects.get(course=self.course, order=6)
        g = les.image_prompts.filter(prompt_type="grammar").first()
        v = les.image_prompts.filter(prompt_type="vocabulary").first()
        gp = effective_image_prompt(g).lower()
        self.assertIn("grammar", gp)
        self.assertIn("plural -s", gp)           # explicit anti-pattern guard
        self.assertTrue(effective_image_prompt(g).startswith(g.prompt))
        # Non-grammar prompts are returned unchanged.
        self.assertEqual(effective_image_prompt(v), v.prompt)

    # 13
    def test_budget_guard_blocks_when_estimate_exceeds_cap(self):
        with patch(_GEN, return_value=_FAKE_PNG) as m:
            rep = self._cmd_json("--apply", "--limit", "12", "--max-cost-usd", "0.001")
        self.assertTrue(rep["budget_exceeded"])
        self.assertEqual(rep["generated_count"], 0)
        m.assert_not_called()
