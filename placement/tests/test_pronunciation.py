from django.test import TestCase

from placement.services.stt import (
    _alignment_accuracy,
    _normalise_word,
    pronunciation_score,
    pronunciation_score_against,
)


class WordAlignmentTests(TestCase):
    def test_normalise_word_strips_punctuation_and_lowercases(self):
        self.assertEqual(_normalise_word("Hello,"), "hello")
        self.assertEqual(_normalise_word("don't"), "don't")
        self.assertEqual(_normalise_word("RUN."), "run")

    def test_alignment_perfect_match(self):
        a = ["the", "quick", "brown", "fox"]
        self.assertEqual(_alignment_accuracy(a, a), 1.0)

    def test_alignment_one_substitution(self):
        a = ["the", "quick", "brown", "fox"]
        b = ["the", "quick", "blue", "fox"]
        self.assertAlmostEqual(_alignment_accuracy(a, b), 0.75, places=2)

    def test_alignment_dropped_words(self):
        a = ["the", "quick", "brown", "fox"]
        b = ["the", "fox"]
        self.assertAlmostEqual(_alignment_accuracy(a, b), 0.5, places=2)

    def test_alignment_empty_returns_zero(self):
        self.assertEqual(_alignment_accuracy([], ["the"]), 0.0)


class PronunciationScoreAgainstTests(TestCase):
    def test_perfect_read_aloud_high_score(self):
        score = pronunciation_score_against(
            transcript="The quick brown fox jumps over the lazy dog",
            expected_text="The quick brown fox jumps over the lazy dog",
            stt_confidence=0.95, fluency=80,
        )
        self.assertGreaterEqual(score, 90)

    def test_total_mismatch_low_score(self):
        score = pronunciation_score_against(
            transcript="apple banana orange",
            expected_text="The quick brown fox jumps",
            stt_confidence=0.5, fluency=40,
        )
        self.assertLess(score, 30)

    def test_partial_match_mid_band(self):
        score = pronunciation_score_against(
            transcript="The quick fox",
            expected_text="The quick brown fox",
            stt_confidence=0.85, fluency=60,
        )
        self.assertGreaterEqual(score, 40)
        self.assertLess(score, 90)

    def test_legacy_score_still_works(self):
        # Sanity check: original heuristic still callable.
        self.assertGreater(
            pronunciation_score("hello world", stt_confidence=0.9, fluency=50),
            0,
        )
