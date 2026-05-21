"""Unit tests for the text humanisation / speech sanitisation layer."""
from django.test import TestCase

from core.services.text_humanizer import (
    SAFE_FALLBACK_AR,
    SAFE_FALLBACK_EN,
    humanize_event_name,
    humanize_field_name,
    humanize_for_speech,
    humanize_technical_tokens,
    humanize_text,
    remove_tts_noise_tokens,
)


class SnakeAndCamelCaseTests(TestCase):
    def test_snake_case_converted(self):
        self.assertEqual(humanize_text("user_profile_updated"), "User profile updated")

    def test_camel_case_converted(self):
        # "weeklyAssessment" → "weekly Assessment" → display preserves casing
        self.assertEqual(humanize_text("weeklyAssessmentScore"), "weekly Assessment Score")

    def test_pascal_case_converted(self):
        self.assertEqual(humanize_text("WeeklyAssessmentScore"), "Weekly Assessment Score")

    def test_double_dashes_cleaned(self):
        self.assertEqual(humanize_text("hello-----world"), "hello world")

    def test_single_inter_word_dash_collapsed(self):
        self.assertEqual(humanize_text("snake-case-thing"), "snake case thing")


class BlankPlaceholderTests(TestCase):
    def test_blank_blank_blank_removed(self):
        self.assertEqual(humanize_text("blank blank blank"), SAFE_FALLBACK_EN)

    def test_null_undefined_runs_removed(self):
        self.assertEqual(humanize_text("hello null undefined world"), "hello world")

    def test_unresolved_django_placeholder_removed(self):
        self.assertEqual(humanize_text("Hello {{ user_name }}"), "Hello")

    def test_unresolved_jinja_block_removed(self):
        self.assertEqual(humanize_text("{% if x %} pending {% endif %}"), "pending")


class EventNameTests(TestCase):
    def test_known_event_english(self):
        self.assertEqual(
            humanize_event_name("payment_approved"), "Payment approved",
        )

    def test_known_event_arabic(self):
        self.assertEqual(
            humanize_event_name("payment_approved", language="ar"), "تم قبول الدفع",
        )

    def test_weekly_assessment_available(self):
        self.assertEqual(
            humanize_event_name("weekly_assessment_available"),
            "Weekly assessment is available",
        )
        self.assertEqual(
            humanize_event_name("weekly_assessment_available", language="ar"),
            "الاختبار الأسبوعي متاح الآن",
        )

    def test_unknown_event_falls_back_to_humanised_key(self):
        self.assertEqual(humanize_event_name("brand_new_event"), "Brand new event")

    def test_empty_event_returns_safe_fallback(self):
        self.assertEqual(humanize_event_name(""), SAFE_FALLBACK_EN)
        self.assertEqual(humanize_event_name("", language="ar"), SAFE_FALLBACK_AR)


class FieldNameTests(TestCase):
    def test_cefr_level_english(self):
        self.assertEqual(humanize_field_name("cefr_level"), "English level")

    def test_cefr_level_arabic(self):
        self.assertEqual(
            humanize_field_name("cefr_level", language="ar"),
            "مستوى اللغة الإنجليزية",
        )

    def test_theta_score(self):
        self.assertEqual(humanize_field_name("theta_score"), "learning ability score")

    def test_unknown_field_split_naturally(self):
        self.assertEqual(humanize_field_name("some_other_field"), "some other field")


class InlineFieldReplacementTests(TestCase):
    def test_theta_score_inline(self):
        out = humanize_text("Your theta_score improved by 12%")
        self.assertEqual(out, "Your learning ability score improved by 12%")

    def test_cefr_level_inline_arabic(self):
        out = humanize_text("Your cefr_level is A2", language="ar")
        self.assertIn("مستوى اللغة الإنجليزية", out)


class SpeechModeTests(TestCase):
    def test_url_dropped_in_speech(self):
        cleaned = humanize_for_speech(
            "Visit https://example.com/path for details"
        )
        self.assertNotIn("http", cleaned)

    def test_file_path_dropped_in_speech(self):
        cleaned = humanize_for_speech("Open /etc/passwd now")
        self.assertNotIn("/etc/passwd", cleaned)

    def test_json_blob_dropped_in_speech(self):
        cleaned = humanize_for_speech('Result: {"score": 92, "id": 12}')
        self.assertNotIn("{", cleaned)
        self.assertNotIn("score", cleaned)

    def test_opaque_id_dropped_in_speech(self):
        cleaned = humanize_for_speech(
            "Token: 8f1c7d8e2c0b4f9b9a6e3a9b8c7d6e5f"
        )
        self.assertNotIn("8f1c7d8e2c0b4f9b9a6e3a9b8c7d6e5f", cleaned)

    def test_cefr_expanded_in_speech_english(self):
        cleaned = humanize_for_speech("You reached A2", language="en")
        self.assertIn("A two level", cleaned)

    def test_cefr_kept_in_speech_arabic(self):
        cleaned = humanize_for_speech("You reached A2", language="ar")
        self.assertIn("المستوى A2", cleaned)

    def test_percent_expanded_in_speech_english(self):
        cleaned = humanize_for_speech("You scored 85% accuracy")
        self.assertIn("85 percent", cleaned)

    def test_percent_expanded_in_speech_arabic(self):
        cleaned = humanize_for_speech("85% دقة", language="ar")
        self.assertIn("85 بالمئة", cleaned)

    def test_markdown_code_fence_stripped(self):
        cleaned = humanize_for_speech("Try this:\n```py\nprint('hi')\n```\nDone.")
        self.assertNotIn("print", cleaned)
        self.assertIn("Done", cleaned)

    def test_inline_code_stripped(self):
        cleaned = humanize_for_speech("Use the `weekly_assessment` model")
        self.assertNotIn("weekly_assessment", cleaned)

    def test_safety_blank_input_returns_fallback(self):
        self.assertEqual(humanize_for_speech("___"), SAFE_FALLBACK_EN)

    def test_safety_none_input_returns_empty(self):
        self.assertEqual(humanize_for_speech(None), "")

    def test_fill_blank_and_punctuation_labels_not_spoken(self):
        cleaned = humanize_for_speech("She ____ (not/like) spicy food comma")
        self.assertNotIn("_", cleaned)
        self.assertNotIn("not/like", cleaned)
        self.assertNotIn("comma", cleaned.lower())
        self.assertIn("She", cleaned)
        self.assertIn("spicy food", cleaned)

    def test_ua_marker_not_spoken(self):
        cleaned = humanize_for_speech("UA user_answer comma ____ is missing")
        self.assertNotRegex(cleaned.lower(), r"\bua\b")
        self.assertNotIn("comma", cleaned.lower())
        self.assertNotIn("_", cleaned)

    def test_real_word_uae_is_preserved(self):
        cleaned = humanize_for_speech("The UAE is a country")
        self.assertIn("UAE", cleaned)

    def test_odd_symbols_are_removed_from_speech(self):
        cleaned = humanize_for_speech(
            "Hello @@@ ### *** <b>world</b> &nbsp; → ✓ star slash backslash"
        )
        for fragment in ["@", "#", "*", "<b>", "&nbsp;", "→", "✓", "star", "slash", "backslash"]:
            self.assertNotIn(fragment, cleaned)
        self.assertIn("Hello", cleaned)
        self.assertIn("world", cleaned)

    def test_normal_sentence_punctuation_is_preserved(self):
        cleaned = humanize_for_speech("Don't stop, please!")
        self.assertEqual(cleaned, "Don't stop, please!")


class PayloadIntegrationTests(TestCase):
    """Real-world snippets mined from notification + motivation payloads."""

    def test_event_string_in_a_sentence_humanised(self):
        out = humanize_text("Status: weekly_assessment_available")
        self.assertEqual(out, "Status: Weekly assessment is available")

    def test_motivation_message_with_field_token(self):
        out = humanize_text(
            "Great work — your theta_score improved this week.",
        )
        self.assertEqual(
            out,
            "Great work — your learning ability score improved this week.",
        )

    def test_arabic_event_in_sentence(self):
        out = humanize_text(
            "حالة: payment_approved",
            language="ar",
        )
        self.assertIn("تم قبول الدفع", out)


class DailyWeeklySpeechTokenTests(TestCase):
    """Covers the /daily + /weekly TTS-noise report: the voice must never
    read underscores, ``UA`` markers, or raw payload keys.
    """

    def test_single_underscore_removed(self):
        self.assertNotIn("_", humanize_for_speech("My name is Ahmed _ here"))

    def test_double_underscore_removed(self):
        self.assertNotIn("_", humanize_for_speech("My name is Ahmed __ here"))

    def test_triple_underscore_removed(self):
        out = humanize_for_speech("My name is Ahmed ___")
        self.assertNotIn("_", out)
        self.assertIn("Ahmed", out)

    def test_ua_underscore_prefix_removed(self):
        # "UA_user_answer" is a hard-banned identifier — dropped whole.
        out = humanize_for_speech("UA_user_answer ___ is missing")
        self.assertNotRegex(out.lower(), r"\bua\b")
        self.assertNotIn("_", out)

    def test_ua_underscore_words_removed(self):
        out = humanize_for_speech("the answer is UA underscore here")
        self.assertNotRegex(out.lower(), r"\bua\b")
        self.assertNotIn("underscore", out.lower())
        self.assertIn("answer", out)

    def test_literal_underscore_word_removed(self):
        self.assertNotIn(
            "underscore", humanize_for_speech("type underscore then go").lower()
        )

    def test_blank_blank_blank_not_spoken(self):
        # A prompt that is only "blank blank blank" cleans to nothing →
        # safe fallback, so the engine never says "blank blank blank".
        self.assertEqual(humanize_for_speech("blank blank blank"), SAFE_FALLBACK_EN)

    def test_user_answer_key_humanised(self):
        self.assertEqual(humanize_field_name("user_answer"), "your answer")
        self.assertEqual(
            humanize_field_name("user_answer", language="ar"), "إجابة الطالب"
        )

    def test_correct_answer_key_humanised(self):
        self.assertEqual(humanize_field_name("correct_answer"), "the correct answer")
        self.assertEqual(
            humanize_field_name("correct_answer", language="ar"), "الإجابة الصحيحة"
        )

    def test_daily_learning_plan_key_humanised(self):
        self.assertEqual(
            humanize_field_name("daily_learning_plan"), "today's learning plan"
        )
        self.assertEqual(
            humanize_field_name("daily_learning_plan", language="ar"), "خطة اليوم"
        )

    def test_weekly_assessment_available_in_speech_arabic(self):
        out = humanize_for_speech("weekly_assessment_available", language="ar")
        self.assertIn("الاختبار الأسبوعي متاح الآن", out)

    def test_json_blob_not_spoken(self):
        out = humanize_for_speech('{"user_answer": "go", "score": 5}')
        self.assertNotIn("{", out)
        self.assertNotIn("score", out)

    def test_normal_english_sentence_untouched(self):
        # The whole point: real learning content survives intact.
        self.assertEqual(
            humanize_for_speech("My name is Ahmed."), "My name is Ahmed."
        )


class RemoveTtsNoiseTokensTests(TestCase):
    def test_strips_underscores_and_ua(self):
        out = remove_tts_noise_tokens("She ____ UA the answer")
        self.assertNotIn("_", out)
        self.assertNotRegex(out.lower(), r"\bua\b")
        self.assertIn("She", out)
        self.assertIn("answer", out)

    def test_strips_hard_banned_prefix(self):
        self.assertNotIn("DB", remove_tts_noise_tokens("value DB_user_id here"))

    def test_does_not_apply_glossary(self):
        # Noise-only: a known key is split, not glossary-translated.
        self.assertNotIn(
            "English level", remove_tts_noise_tokens("cefr_level matters")
        )

    def test_none_input_safe(self):
        self.assertEqual(remove_tts_noise_tokens(None), "")


class HumanizeTechnicalTokensTests(TestCase):
    def test_maps_known_field_key(self):
        self.assertIn(
            "English level", humanize_technical_tokens("cefr_level", language="en")
        )

    def test_maps_known_event_key_arabic(self):
        self.assertIn(
            "الاختبار الأسبوعي متاح الآن",
            humanize_technical_tokens("weekly_assessment_available", language="ar"),
        )

    def test_splits_unknown_snake_case(self):
        self.assertEqual(
            humanize_technical_tokens("some_unknown_key", language="en"),
            "some unknown key",
        )

    def test_none_input_safe(self):
        self.assertEqual(humanize_technical_tokens(None), "")
