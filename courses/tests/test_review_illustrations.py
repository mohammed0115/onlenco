"""Prompt 18.2E — review & approve generated Beginner illustrations."""
from __future__ import annotations

import json
import os
import tempfile
from io import StringIO

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase

from courses.models import Course, Lesson, LessonAudioScript, LessonImagePrompt


class ReviewBeginnerIllustrationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units", "--quiet")
        cls.course = Course.objects.get(slug="onlenco-beginner")

    def _gen_illus(self, order, ptype, *, with_file=True, status="needs_review"):
        p = (Lesson.objects.get(course=self.course, order=order)
             .image_prompts.filter(prompt_type=ptype).first())
        if with_file:
            p.generated_image.save(f"{ptype}{order}.png", ContentFile(b"imgbytes"), save=False)
        p.generation_status = status
        p.save()
        return p

    def _review_json(self, *args):
        out = StringIO()
        call_command("review_beginner_illustrations", "--format", "json", *args, stdout=out)
        return json.loads(out.getvalue())

    # 1
    def test_command_exists(self):
        rep = self._review_json()
        self.assertIn("total_reviewed", rep)
        self.assertEqual(rep["types"], ["vocabulary", "grammar", "quiz"])

    # 2
    def test_lists_only_needs_review_generated_illustrations(self):
        self._gen_illus(1, "vocabulary")                       # needs_review
        self._gen_illus(2, "grammar", status="approved")       # already approved
        rep = self._review_json("--from-book-unit", "1", "--to-book-unit", "4")
        ids_types = {(r["book_unit_number"], r["image_type"]) for r in rep["items"]}
        self.assertIn((1, "vocabulary"), ids_types)
        self.assertNotIn((2, "grammar"), ids_types)  # approved excluded by status filter

    # 3
    def test_dry_run_does_not_modify_db(self):
        p = self._gen_illus(1, "vocabulary")
        self._review_json("--approve")  # no --apply → dry-run
        p.refresh_from_db()
        self.assertEqual(p.generation_status, "needs_review")

    # 4
    def test_does_not_touch_cover_images(self):
        cover = self._gen_illus(1, "cover")  # cover with file, needs_review
        self._review_json("--approve", "--apply")
        cover.refresh_from_db()
        self.assertNotEqual(cover.generation_status, "approved")

    # 5
    def test_does_not_touch_audio(self):
        s = Lesson.objects.get(course=self.course, order=1).audio_scripts.first()
        s.generated_audio.save("a.mp3", ContentFile(b"x"), save=False)
        s.generation_status = "needs_review"
        s.save()
        self._gen_illus(1, "vocabulary")
        self._review_json("--approve", "--apply")
        s.refresh_from_db()
        self.assertNotEqual(s.generation_status, "approved")

    # 6
    def test_does_not_touch_noncanonical_lessons(self):
        legacy = Lesson.objects.create(
            course=self.course, title="Legacy", order=99, book_unit_number=99)
        p = LessonImagePrompt.objects.create(
            lesson=legacy, prompt_type="vocabulary", prompt="x",
            generation_status="needs_review")
        p.generated_image.save("l.png", ContentFile(b"img"), save=True)
        self._review_json("--approve", "--apply")
        p.refresh_from_db()
        self.assertNotEqual(p.generation_status, "approved")

    # 7
    def test_manifest_contains_book_unit_and_image_type(self):
        self._gen_illus(1, "vocabulary")
        path = os.path.join(tempfile.mkdtemp(), "manifest.json")
        self._review_json("--from-book-unit", "1", "--to-book-unit", "4",
                          "--export-manifest", path)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertGreaterEqual(data["count"], 1)
        item = data["items"][0]
        self.assertIn("book_unit_number", item)
        self.assertIn("image_type", item)

    # 8
    def test_approve_marks_only_eligible_illustrations(self):
        a = self._gen_illus(1, "vocabulary")
        b = self._gen_illus(2, "grammar")
        rep = self._review_json("--approve", "--apply")
        self.assertEqual(rep["approved_count"], 2)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(a.generation_status, "approved")
        self.assertEqual(b.generation_status, "approved")

    # 9
    def test_approve_makes_images_student_visible(self):
        p = self._gen_illus(1, "vocabulary")
        self._review_json("--approve", "--apply")
        p.refresh_from_db()
        self.assertTrue(p.is_student_visible)

    # 10
    def test_approve_is_idempotent(self):
        self._gen_illus(1, "vocabulary")
        self._review_json("--approve", "--apply")
        rep2 = self._review_json("--approve", "--apply")
        self.assertEqual(rep2.get("approved_count", 0), 0)

    # 11
    def test_does_not_approve_missing_file(self):
        p = self._gen_illus(1, "vocabulary", with_file=False)  # needs_review, no file
        self._review_json("--approve", "--apply")
        p.refresh_from_db()
        self.assertNotEqual(p.generation_status, "approved")

    # 12
    def test_does_not_approve_duplicates(self):
        a = self._gen_illus(1, "vocabulary")
        dup = LessonImagePrompt.objects.create(
            lesson=a.lesson, prompt_type="vocabulary", prompt="dup",
            generation_status="needs_review")
        dup.generated_image.save("dup.png", ContentFile(b"img"), save=True)
        rep = self._review_json("--approve", "--apply")
        a.refresh_from_db(); dup.refresh_from_db()
        self.assertGreaterEqual(rep["skipped_duplicate"], 2)
        self.assertNotEqual(a.generation_status, "approved")
        self.assertNotEqual(dup.generation_status, "approved")

    # 13
    def test_audit_after_approval_reports_approved_illustration(self):
        # Fresh seed: covers have no file → approving an illustration makes that
        # lesson have an approved, student-visible image.
        self._gen_illus(1, "vocabulary")
        self._review_json("--approve", "--apply")
        out = StringIO()
        call_command("audit_beginner_media", "--format", "json", stdout=out)
        a = json.loads(out.getvalue())
        self.assertGreaterEqual(a["images"]["lessons_with_approved_image"], 1)
