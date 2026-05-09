"""Tests for `question_factory.services.question_quality_gate`.

Mapped to the spec's 7 required test cases plus coverage of the
remaining rules and the annotate/passes helpers."""
from django.test import TestCase

from question_factory.models import GeneratedQuestion
from question_factory.services import question_quality_gate as gate
from question_factory.services.duplicate_detector import hash_question


def _good_item(**overrides) -> dict:
    item = {
        "question_text": "She ___ to school every day.",
        "correct_answer": "goes",
        "options": ["go", "goes", "going", "gone"],
        "question_type": "multiple_choice",
        "cefr_level": "A1",
        "skill": "grammar",
        "difficulty_score": 0.30,
        "explanation": "Use the third-person singular '-s' with 'she'.",
        "language": "en",
    }
    item.update(overrides)
    return item


# ---------------------------------------------------------------------------
# Spec-required tests (7)
# ---------------------------------------------------------------------------

class QualityGateSpecTests(TestCase):
    # 1. valid question accepted -----------------------------------

    def test_valid_question_accepted(self):
        result = gate.evaluate(_good_item(), check_db_duplicate=False)
        self.assertTrue(result.accepted)
        self.assertFalse(result.review_required)
        self.assertEqual(result.quality_score, 100)
        self.assertEqual(result.failed_rules, [])
        self.assertEqual(result.rejection_reason, "")

    # 2. empty question rejected -----------------------------------

    def test_empty_question_rejected(self):
        result = gate.evaluate(_good_item(question_text=""),
                               check_db_duplicate=False)
        self.assertFalse(result.accepted)
        self.assertIn(gate.R_EMPTY_QUESTION, result.failed_rules)
        self.assertTrue(result.rejection_reason.startswith("critical:"))

    # 3. MCQ missing answer rejected -------------------------------

    def test_mcq_missing_answer_rejected(self):
        # Either an empty correct_answer or an answer not in options counts.
        empty_ans = gate.evaluate(_good_item(correct_answer=""),
                                  check_db_duplicate=False)
        self.assertFalse(empty_ans.accepted)
        self.assertIn(gate.R_EMPTY_ANSWER, empty_ans.failed_rules)

        not_in_opts = gate.evaluate(_good_item(correct_answer="zzz"),
                                    check_db_duplicate=False)
        self.assertFalse(not_in_opts.accepted)
        self.assertIn(gate.R_ANSWER_NOT_IN_OPTS, not_in_opts.failed_rules)

    # 4. unresolved placeholder rejected ---------------------------

    def test_unresolved_placeholder_rejected(self):
        result = gate.evaluate(
            _good_item(question_text="She {{verb}} to school."),
            check_db_duplicate=False,
        )
        self.assertFalse(result.accepted)
        self.assertIn(gate.R_PLACEHOLDER, result.failed_rules)

    # 5. technical token rejected ----------------------------------

    def test_technical_token_rejected(self):
        # snake_case tokens
        snake = gate.evaluate(
            _good_item(question_text="The question_type is multiple_choice."),
            check_db_duplicate=False,
        )
        self.assertFalse(snake.accepted)
        self.assertIn(gate.R_TECH_TOKEN, snake.failed_rules)

        # double-dash CLI flag
        dashes = gate.evaluate(
            _good_item(question_text="Use --quiet to silence."),
            check_db_duplicate=False,
        )
        self.assertFalse(dashes.accepted)
        self.assertIn(gate.R_TECH_TOKEN, dashes.failed_rules)

    def test_fill_blank_marker_is_not_a_technical_token(self):
        """The '___' marker is *intended* — must not trip rule 12."""
        result = gate.evaluate(_good_item(), check_db_duplicate=False)
        self.assertNotIn(gate.R_TECH_TOKEN, result.failed_rules)

    # 6. duplicate rejected ----------------------------------------

    def test_exact_duplicate_rejected(self):
        item = _good_item()
        # Seed a row with the same content_hash that the gate will compute.
        h = hash_question(item["question_text"], item["correct_answer"])
        GeneratedQuestion.objects.create(
            code="dup-row", question_type="multiple_choice",
            question_text=item["question_text"],
            correct_answer=item["correct_answer"],
            options=item["options"],
            content_hash=h,
        )
        result = gate.evaluate(item)  # check_db_duplicate=True is default
        self.assertFalse(result.accepted)
        self.assertIn(gate.R_EXACT_DUPLICATE, result.failed_rules)
        self.assertIn("duplicate_match", result.metadata)

    # 7. low quality marked review_required -----------------------

    def test_low_quality_marked_review_required(self):
        # Two soft failures: invalid skill (-20) + missing explanation (-10)
        # → score 70, no critical → accepted but review_required.
        item = _good_item(skill="not-a-real-skill", explanation="")
        result = gate.evaluate(item, check_db_duplicate=False)
        self.assertTrue(result.accepted)
        self.assertTrue(result.review_required)
        self.assertGreaterEqual(result.quality_score, 60)
        self.assertLess(result.quality_score, 80)
        self.assertIn(gate.R_INVALID_SKILL, result.failed_rules)
        self.assertIn(gate.R_MISSING_EXPLANATION, result.failed_rules)


# ---------------------------------------------------------------------------
# Additional coverage of the remaining rules
# ---------------------------------------------------------------------------

class QualityGateRuleCoverageTests(TestCase):

    def test_mcq_too_few_options_rejected(self):
        result = gate.evaluate(_good_item(options=["a", "goes"]),
                               check_db_duplicate=False)
        self.assertFalse(result.accepted)
        self.assertIn(gate.R_MCQ_OPTIONS_MIN, result.failed_rules)

    def test_duplicate_options_rejected(self):
        result = gate.evaluate(
            _good_item(options=["go", "go", "going", "gone"]),
            check_db_duplicate=False,
        )
        self.assertFalse(result.accepted)
        self.assertIn(gate.R_DUPLICATE_OPTIONS, result.failed_rules)

    def test_invalid_cefr_rejected(self):
        result = gate.evaluate(_good_item(cefr_level="ZZ"),
                               check_db_duplicate=False)
        self.assertFalse(result.accepted)
        self.assertIn(gate.R_INVALID_CEFR, result.failed_rules)

    def test_difficulty_out_of_range_flagged(self):
        result = gate.evaluate(_good_item(difficulty_score=2.0),
                               check_db_duplicate=False)
        self.assertIn(gate.R_DIFF_OUT_OF_RANGE, result.failed_rules)

    def test_blank_run_rejected(self):
        result = gate.evaluate(
            _good_item(question_text="Fill blank blank blank now."),
            check_db_duplicate=False,
        )
        self.assertFalse(result.accepted)
        self.assertIn(gate.R_BLANK_RUN, result.failed_rules)

    def test_offensive_content_rejected(self):
        result = gate.evaluate(
            _good_item(explanation="What the fuck is this?"),
            check_db_duplicate=False,
        )
        self.assertFalse(result.accepted)
        self.assertIn(gate.R_OFFENSIVE, result.failed_rules)

    def test_private_data_flagged(self):
        result = gate.evaluate(
            _good_item(explanation="Email me at sara@example.com please."),
            check_db_duplicate=False,
        )
        # Private data is soft → still might pass on score — but flagged.
        self.assertIn(gate.R_PRIVATE_DATA, result.failed_rules)

    def test_answer_question_mismatch_flagged(self):
        # Answer ends in '?' but question doesn't — semantic mismatch.
        result = gate.evaluate(
            _good_item(question_text="What is your name.",
                       correct_answer="What is yours?"),
            check_db_duplicate=False,
        )
        # Note: 'What is yours?' isn't in the options either, so the
        # critical rule fires too. But we should also see the mismatch.
        self.assertIn(gate.R_ANSWER_MISMATCH, result.failed_rules)

    def test_wrong_language_for_arabic_flagged(self):
        result = gate.evaluate(
            _good_item(language="ar"),  # text is English but language=ar
            check_db_duplicate=False,
        )
        self.assertIn(gate.R_WRONG_LANGUAGE, result.failed_rules)

    def test_invalid_language_flagged(self):
        result = gate.evaluate(_good_item(language="zz"),
                               check_db_duplicate=False)
        self.assertIn(gate.R_WRONG_LANGUAGE, result.failed_rules)

    def test_level_difficulty_mismatch_flagged(self):
        # A1 with very high difficulty 0.95 → outside band 0.05–0.40 (+0.10).
        result = gate.evaluate(
            _good_item(difficulty_score=0.95),
            check_db_duplicate=False,
        )
        self.assertIn(gate.R_LEVEL_DIFF_MISMATCH, result.failed_rules)


# ---------------------------------------------------------------------------
# Helper API: passes() and annotate()
# ---------------------------------------------------------------------------

class QualityGateAPITests(TestCase):
    def test_passes_returns_bool(self):
        self.assertTrue(gate.passes(_good_item(), check_db_duplicate=False))
        self.assertFalse(
            gate.passes(_good_item(question_text=""), check_db_duplicate=False)
        )

    def test_annotate_stamps_metadata(self):
        item = _good_item()
        gate.annotate(item, check_db_duplicate=False)
        self.assertEqual(item["quality_score"], 100)
        self.assertIn("quality_gate", item["metadata"])
        gate_md = item["metadata"]["quality_gate"]
        self.assertTrue(gate_md["accepted"])
        self.assertEqual(gate_md["failed_rules"], [])
        self.assertTrue(item["is_reviewed"])

    def test_annotate_sets_is_reviewed_false_when_review_required(self):
        item = _good_item(skill="bogus", explanation="")
        gate.annotate(item, check_db_duplicate=False)
        self.assertFalse(item["is_reviewed"])
        self.assertTrue(item["metadata"]["quality_gate"]["review_required"])

    def test_gate_result_is_serialisable(self):
        result = gate.evaluate(_good_item(), check_db_duplicate=False)
        d = result.to_dict()
        self.assertEqual(d["accepted"], True)
        self.assertEqual(d["quality_score"], 100)
        self.assertIn("failed_rules", d)
        self.assertIn("metadata", d)
