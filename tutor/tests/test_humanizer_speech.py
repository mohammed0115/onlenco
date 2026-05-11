"""Lock the TextHumanizer speech-mode contract.

The TTS path runs every reply through `humanize_for_speech()` before
playing it. The cleanups required by the AI Tutor spec (no underscores,
no `--` runs, no "blank blank blank", no raw event names, no JSON, no
technical fields) all live in that one function. These tests pin them
so a future glossary edit can't silently regress speech quality.
"""
from __future__ import annotations

from django.test import TestCase

from core.services.text_humanizer import (
    humanize_for_speech,
    humanize_text,
)


class HumanizerSpeechCleanupTests(TestCase):
    def test_underscore_words_become_spaced(self):
        # snake_case identifiers must never be spoken as "user underscore profile".
        out = humanize_for_speech("Your user_profile_updated event fired.")
        self.assertNotIn("_", out)
        self.assertIn("profile", out.lower())

    def test_long_dash_runs_collapse(self):
        # `--` and longer runs must not be spoken as "dash dash".
        out = humanize_for_speech("Great work -- keep it up --- well done")
        self.assertNotIn("--", out)
        self.assertIn("Great work", out)
        self.assertIn("keep it up", out)

    def test_blank_runs_strip(self):
        # The model occasionally emits "blank blank blank" placeholders.
        out = humanize_for_speech("Try this: blank blank blank tomorrow.")
        self.assertNotIn("blank blank", out.lower())
        self.assertIn("Try this", out)

    def test_raw_event_name_replaced(self):
        # Glossary maps `user_registered` → user-facing phrase.
        out = humanize_for_speech("Status: user_registered")
        self.assertNotIn("user_registered", out)

    def test_json_blob_dropped(self):
        # JSON-ish chunks are unspeakable; drop them.
        out = humanize_for_speech('Result {"ok": true, "id": 42} was saved.')
        self.assertNotIn("{", out)
        self.assertNotIn("}", out)
        self.assertIn("Result", out)
        self.assertIn("saved", out)

    def test_technical_field_name_translated(self):
        # `cefr_level` → "English level" (per default field glossary).
        out = humanize_for_speech("Your cefr_level just went up.")
        self.assertNotIn("cefr_level", out)

    def test_url_dropped_from_speech(self):
        out = humanize_for_speech("See https://example.com/path for details.")
        self.assertNotIn("http", out)
        self.assertIn("details", out)

    def test_cefr_token_expanded_for_natural_reading(self):
        out = humanize_for_speech("Your level is A1.")
        # English: A1 → "A one level"
        self.assertIn("one", out.lower())
        self.assertNotIn("A1", out)

    def test_arabic_speech_preserves_cefr_token(self):
        out = humanize_for_speech("مستواك A1", language="ar")
        # Arabic readers want the level kept verbatim alongside an Arabic prefix.
        self.assertIn("A1", out)

    def test_empty_input_returns_safe_fallback(self):
        # Never let the TTS layer try to speak an empty string.
        self.assertNotEqual(humanize_for_speech(""), "")
        self.assertNotEqual(humanize_for_speech("    "), "")

    def test_display_mode_keeps_markdown(self):
        # Display mode (used in the chat bubble) does NOT strip markdown
        # so a tutor reply with `**bold**` survives in the transcript.
        out = humanize_text("Try **this** instead", mode="display")
        self.assertIn("**this**", out)
