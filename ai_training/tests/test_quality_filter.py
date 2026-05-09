from django.test import TestCase

from ai_training.services import dataset_quality_filter as f


def _example(**overrides):
    base = {
        "task_type": "exercise_generation",
        "input": {
            "cefr_level": "A1",
            "skill": "grammar",
            "topic": "present_simple",
            "difficulty": 0.3,
        },
        "output": {
            "question": "She ___ to school every day.",
            "options": ["go", "goes", "going", "gone"],
            "correct_answer": "goes",
            "explanation": "Add -s for the third person singular.",
        },
        "cefr_level": "A1",
        "skill": "grammar",
        "quality_score": 90,
    }
    base.update(overrides)
    return base


class QualityFilterTests(TestCase):
    def test_clean_example_passes(self):
        cleaned, reasons = f.clean_and_filter(_example(), min_quality=60)
        self.assertIsNotNone(cleaned)
        self.assertEqual(reasons, [])
        self.assertTrue(cleaned["content_hash"])

    def test_low_quality_rejected(self):
        cleaned, reasons = f.clean_and_filter(
            _example(quality_score=30), min_quality=60,
        )
        self.assertIsNone(cleaned)
        self.assertIn(f.REASON_LOW_QUALITY, reasons)

    def test_private_data_redacted(self):
        sample = _example()
        sample["output"]["explanation"] = (
            "Email me at sara.smith@example.com or call +1 555-123-4567."
        )
        cleaned, reasons = f.clean_and_filter(sample, min_quality=60)
        self.assertIsNotNone(cleaned)
        self.assertIn(f.REASON_PRIVATE_DATA, reasons)
        self.assertNotIn("@example.com", cleaned["output"]["explanation"])
        self.assertIn("[REDACTED-EMAIL]", cleaned["output"]["explanation"])

    def test_technical_token_rejected(self):
        sample = _example()
        sample["output"]["explanation"] = "Use ```code``` here."
        cleaned, reasons = f.clean_and_filter(sample, min_quality=60)
        self.assertIsNone(cleaned)
        self.assertIn(f.REASON_TECH_TOKEN, reasons)

    def test_unresolved_placeholder_rejected(self):
        sample = _example()
        sample["output"]["question"] = "She {{verb}} home."
        cleaned, reasons = f.clean_and_filter(sample, min_quality=60)
        self.assertIsNone(cleaned)
        self.assertIn(f.REASON_TECH_TOKEN, reasons)

    def test_invalid_cefr_rejected(self):
        cleaned, reasons = f.clean_and_filter(
            _example(cefr_level="ZZ"), min_quality=60,
        )
        self.assertIsNone(cleaned)
        self.assertIn(f.REASON_INVALID_CEFR, reasons)

    def test_cefr_normalised_to_upper(self):
        cleaned, _ = f.clean_and_filter(_example(cefr_level="a1"), min_quality=60)
        self.assertEqual(cleaned["cefr_level"], "A1")

    def test_empty_output_rejected(self):
        cleaned, reasons = f.clean_and_filter(
            _example(output={}), min_quality=60,
        )
        self.assertIsNone(cleaned)

    def test_content_hash_is_deterministic_after_cleaning(self):
        a, _ = f.clean_and_filter(_example(), min_quality=60)
        b, _ = f.clean_and_filter(_example(), min_quality=60)
        self.assertEqual(a["content_hash"], b["content_hash"])

    def test_content_hash_changes_with_input(self):
        s1 = _example()
        s2 = _example()
        s2["output"]["question"] = "He ___ to school every day."
        a, _ = f.clean_and_filter(s1, min_quality=60)
        b, _ = f.clean_and_filter(s2, min_quality=60)
        self.assertNotEqual(a["content_hash"], b["content_hash"])
