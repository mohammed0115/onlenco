"""Placement result transparency: answer key, MCQ grading, ✓/✗ on result page."""
from django.test import TestCase

from placement.services import answer_key
from placement.services.dynamic_scoring import _score_written_item


MCQ_OPTS = [
    {"text": "went", "is_correct": True},
    {"text": "goed", "is_correct": False},
    {"text": "go", "is_correct": False},
]


class AnswerKeyHelperTests(TestCase):
    def test_mcq_correct_answer_and_grading(self):
        self.assertEqual(answer_key.correct_answer_for(options=MCQ_OPTS, expected_type="mcq"), "went")
        self.assertTrue(answer_key.is_answer_correct("went", options=MCQ_OPTS, expected_type="mcq"))
        self.assertFalse(answer_key.is_answer_correct("goed", options=MCQ_OPTS, expected_type="mcq"))
        self.assertTrue(answer_key.is_answer_correct(" WENT ", options=MCQ_OPTS, expected_type="mcq"))

    def test_legacy_string_options_have_no_key(self):
        self.assertIsNone(answer_key.is_answer_correct("a", options=["a", "b"], expected_type="mcq"))

    def test_text_expected_answer(self):
        rubric = {"expected_answer": "I am fine", "accepted_answers": ["I'm fine"]}
        self.assertTrue(answer_key.is_answer_correct("i am fine", rubric=rubric, expected_type="sentence"))
        self.assertTrue(answer_key.is_answer_correct("I'm fine", rubric=rubric, expected_type="sentence"))
        self.assertFalse(answer_key.is_answer_correct("no", rubric=rubric, expected_type="sentence"))

    def test_open_ended_text_has_no_exact_key(self):
        self.assertIsNone(answer_key.is_answer_correct("anything", rubric={}, expected_type="paragraph"))

    def test_voice_keywords(self):
        rubric = {"voice_keywords": ["name", "country"]}
        self.assertIn("name", answer_key.correct_answer_for(rubric=rubric, expected_type="voice"))


class McqScoringTests(TestCase):
    def _item(self, answer):
        return {
            "section": "written", "expected_answer_type": "mcq",
            "options": MCQ_OPTS, "scoring_rubric": {}, "answer": answer,
            "attempt_question_id": 1,
        }

    def test_correct_mcq_scores_100(self):
        row = _score_written_item(self._item("went"), "went")
        self.assertEqual(row["score"], 100)

    def test_wrong_mcq_scores_0(self):
        row = _score_written_item(self._item("goed"), "goed")
        self.assertEqual(row["score"], 0)
