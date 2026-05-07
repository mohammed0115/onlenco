import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from library.models import (
    Book,
    Chapter,
    ComprehensionQuestion,
    GrammarExtract,
    VocabularyExtract,
)
from library.services.extractors import extract_chapter_lessons


class ExtractorTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            title="The Story", category="short", level="A2"
        )
        self.chapter = Chapter.objects.create(
            book=self.book,
            title="Morning routine",
            body=(
                "Every morning Sarah wakes up at six o'clock. She washes her face, "
                "drinks tea with her mother, and walks to school with her brother."
            ),
            sort_order=1,
        )

    @override_settings(AI_API_KEY="")
    def test_heuristic_fallback_creates_some_rows(self):
        counts = extract_chapter_lessons(self.chapter)
        self.assertGreaterEqual(counts["vocabulary"], 1)
        self.assertGreaterEqual(counts["grammar"], 1)
        self.assertGreaterEqual(counts["comprehension"], 1)
        self.assertTrue(VocabularyExtract.objects.filter(chapter=self.chapter).exists())

    @override_settings(AI_API_KEY="key", AI_API_BASE="https://x", AI_MODEL="m")
    def test_ai_path_persists_rows(self):
        from library.services import extractors

        envelope = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "arguments": json.dumps(
                                        {
                                            "vocabulary": [
                                                {"term": "wake up", "translation": "يستيقظ"}
                                            ],
                                            "grammar": [
                                                {"topic": "Present simple", "explanation": "Daily routines."}
                                            ],
                                            "comprehension": [
                                                {
                                                    "question": "What time does Sarah wake up?",
                                                    "options": ["five", "six", "seven"],
                                                    "correct_answer": "six",
                                                    "explanation": "Stated directly.",
                                                }
                                            ],
                                        }
                                    )
                                }
                            }
                        ]
                    }
                }
            ]
        }

        class R:
            status_code = 200

            def json(self_inner):
                return envelope

            def raise_for_status(self_inner):
                pass

        with patch.object(extractors.requests, "post", return_value=R()):
            counts = extract_chapter_lessons(self.chapter)

        self.assertEqual(counts["vocabulary"], 1)
        self.assertEqual(counts["grammar"], 1)
        self.assertEqual(counts["comprehension"], 1)
        self.assertEqual(VocabularyExtract.objects.get(chapter=self.chapter).term, "wake up")

    @override_settings(AI_API_KEY="")
    def test_extraction_is_idempotent(self):
        extract_chapter_lessons(self.chapter)
        v1 = VocabularyExtract.objects.filter(chapter=self.chapter).count()
        extract_chapter_lessons(self.chapter)
        v2 = VocabularyExtract.objects.filter(chapter=self.chapter).count()
        self.assertEqual(v1, v2)
