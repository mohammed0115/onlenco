"""Per-rule coverage for the question-quality validator. Each test
exercises one rule so a regression is easy to localise."""
from django.test import TestCase

from exams.services.question_quality import evaluate, passes


def _base_item(**overrides) -> dict:
    item = {
        "question": "She ___ to the office every day.",
        "correct_answer": "goes",
        "options": ["go", "goes", "going", "gone"],
        "question_type": "multiple_choice",
        "difficulty_score": 0.4,
        "cefr_level": "A1",
        "language": "en",
    }
    item.update(overrides)
    return item


class QualityRuleTests(TestCase):
    def test_clean_item_scores_100(self):
        score, fails = evaluate(_base_item())
        self.assertEqual(fails, [])
        self.assertEqual(score, 100)

    def test_question_too_short(self):
        _, fails = evaluate(_base_item(question="ok"))
        self.assertIn("question_too_short", fails)

    def test_missing_correct_answer(self):
        _, fails = evaluate(_base_item(correct_answer=""))
        self.assertIn("missing_correct_answer", fails)

    def test_mcq_needs_4_options(self):
        _, fails = evaluate(_base_item(options=["a", "b"]))
        self.assertIn("mcq_needs_4_options", fails)

    def test_correct_answer_not_in_options(self):
        _, fails = evaluate(_base_item(correct_answer="nope"))
        self.assertIn("correct_answer_not_in_options", fails)

    def test_difficulty_out_of_range(self):
        _, fails = evaluate(_base_item(difficulty_score=2.0))
        self.assertIn("difficulty_out_of_range", fails)

    def test_difficulty_not_numeric(self):
        _, fails = evaluate(_base_item(difficulty_score="hard"))
        self.assertIn("difficulty_not_numeric", fails)

    def test_invalid_cefr(self):
        _, fails = evaluate(_base_item(cefr_level="Z9"))
        self.assertIn("invalid_cefr", fails)

    def test_unresolved_placeholder(self):
        _, fails = evaluate(_base_item(question="She {{verb}} to school."))
        self.assertIn("unresolved_placeholder", fails)

    def test_blank_run(self):
        _, fails = evaluate(_base_item(question="She blank blank blank goes."))
        self.assertIn("blank_run", fails)

    def test_offensive_in_correct_answer(self):
        score, fails = evaluate(_base_item(correct_answer="shit"))
        self.assertIn("offensive", fails)
        self.assertLessEqual(score, 50)

    def test_invalid_language(self):
        _, fails = evaluate(_base_item(language="xx"))
        self.assertIn("invalid_language", fails)

    def test_passes_threshold_gate(self):
        self.assertTrue(passes(_base_item(), threshold=60))
        bad = _base_item(question="ok", correct_answer="")
        self.assertFalse(passes(bad, threshold=60))
