"""Tests for the auto-course management command."""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from daily_learning.services import a0_templates
from library.models import Book, Chapter


class SeedA0AudioCourseTests(TestCase):
    def test_command_creates_one_book_and_one_chapter_per_topic(self):
        out = StringIO()
        call_command("seed_a0_audio_course", stdout=out)
        book = Book.objects.get(title="Onlenco A0 — First Words")
        self.assertEqual(book.level, "A0")
        self.assertTrue(book.is_published)
        # Exactly one chapter per A0 topic.
        self.assertEqual(
            book.chapters.count(),
            len(a0_templates.A0_TOPICS),
        )

    def test_chapters_are_in_catalog_order_and_titled_correctly(self):
        call_command("seed_a0_audio_course", stdout=StringIO())
        book = Book.objects.get(title="Onlenco A0 — First Words")
        chapters = list(book.chapters.order_by("sort_order"))
        for ch, topic in zip(chapters, a0_templates.A0_TOPICS):
            self.assertEqual(ch.title, topic.title_en,
                             f"Chapter sort={ch.sort_order} title mismatch")

    def test_chapter_body_contains_target_word_and_sentence(self):
        call_command("seed_a0_audio_course", stdout=StringIO())
        book = Book.objects.get(title="Onlenco A0 — First Words")
        first = book.chapters.order_by("sort_order").first()
        topic = a0_templates.A0_TOPICS[0]
        self.assertIn(topic.target_word, first.body)
        self.assertIn(topic.target_sentence, first.body)

    def test_chapter_body_is_bilingual(self):
        """Chapter body must contain Arabic glyphs so beginners can
        self-study from the Library page."""
        import re
        call_command("seed_a0_audio_course", "--force", stdout=StringIO())
        book = Book.objects.get(title="Onlenco A0 — First Words")
        first = book.chapters.order_by("sort_order").first()
        # Arabic Unicode block.
        self.assertRegex(
            first.body, r"[؀-ۿ]",
            "Chapter body must contain Arabic characters for A0 readers",
        )
        self.assertIn("الكلمة", first.body, "AR section header expected")
        self.assertIn("الجملة", first.body, "AR section header expected")

    def test_duration_seconds_is_estimated(self):
        call_command("seed_a0_audio_course", stdout=StringIO())
        book = Book.objects.get(title="Onlenco A0 — First Words")
        for ch in book.chapters.all():
            self.assertGreaterEqual(
                ch.duration_seconds, 15,
                "Every chapter should have at least the minimum duration",
            )

    def test_rerun_is_idempotent_no_duplicates(self):
        call_command("seed_a0_audio_course", stdout=StringIO())
        call_command("seed_a0_audio_course", stdout=StringIO())
        self.assertEqual(
            Book.objects.filter(title="Onlenco A0 — First Words").count(),
            1,
        )
        book = Book.objects.get(title="Onlenco A0 — First Words")
        self.assertEqual(
            book.chapters.count(),
            len(a0_templates.A0_TOPICS),
        )

    def test_rerun_preserves_edited_bodies_unless_force(self):
        """Operator edits to chapter bodies survive a normal re-run."""
        call_command("seed_a0_audio_course", stdout=StringIO())
        book = Book.objects.get(title="Onlenco A0 — First Words")
        ch = book.chapters.order_by("sort_order").first()
        ch.body = "OPERATOR EDIT — leave me alone"
        ch.save(update_fields=["body"])

        call_command("seed_a0_audio_course", stdout=StringIO())  # no --force
        ch.refresh_from_db()
        self.assertIn("OPERATOR EDIT", ch.body,
                      "Re-running without --force must keep edits")

        call_command("seed_a0_audio_course", "--force", stdout=StringIO())
        ch.refresh_from_db()
        self.assertNotIn("OPERATOR EDIT", ch.body,
                         "--force must overwrite the edit back to auto body")
