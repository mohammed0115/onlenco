from unittest.mock import patch

from django.test import TestCase, override_settings

from library.models import Book, Chapter
from library.services.summarizer import _heuristic_summary, summarize_chapter


class HeuristicSummaryTests(TestCase):
    def test_empty_input_returns_empty(self):
        out = _heuristic_summary("", language="en")
        self.assertEqual(out["summary"], "")
        self.assertEqual(out["source"], "heuristic")

    def test_extracts_first_and_last_sentences(self):
        text = "First sentence. Second one is longer. " + "Filler. " * 5 + "Final closing line."
        out = _heuristic_summary(text, language="en")
        self.assertIn("First sentence", out["summary"])
        self.assertEqual(out["source"], "heuristic")


class SummarizeChapterTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            title="Demo", category="article", level="A2",
        )
        self.chapter = Chapter.objects.create(
            book=self.book, title="Ch", body="One. Two long sentence. " * 8,
            sort_order=1,
        )

    @override_settings(AI_API_KEY="")
    def test_no_ai_falls_back_to_heuristic(self):
        out = summarize_chapter(self.chapter)
        self.assertEqual(out["source"], "heuristic")
        self.assertTrue(out["summary"])

    @override_settings(AI_API_KEY="sk-test")
    def test_ai_failure_falls_back(self):
        with patch("library.services.summarizer.requests.post",
                   side_effect=RuntimeError("net")):
            out = summarize_chapter(self.chapter)
        self.assertEqual(out["source"], "heuristic")
