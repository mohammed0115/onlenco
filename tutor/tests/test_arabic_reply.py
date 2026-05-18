"""Language-preference rule branches on BOTH UI lang AND CEFR level.

Arabic UI alone is not enough to flip the tutor to Arabic-primary —
that would over-help B1+ students who came here to practise English.
The rule now: Arabic UI + (A0 OR A1) → Arabic-primary; everyone else
gets English-primary.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from tutor.services._chat import _system_prompt
from tutor.services.context_builder import build_tutor_context

User = get_user_model()


class LanguagePreferencePromptTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ar@x.com", password="pw")

    def _ctx(self, lang: str, cefr: str = "B1"):
        self.user.profile.preferred_language = lang
        self.user.profile.cefr_level = cefr
        self.user.profile.save(update_fields=["preferred_language", "cefr_level"])
        return build_tutor_context(self.user)

    def test_arabic_pref_beginner_a0_gets_arabic_primary(self):
        prompt = _system_prompt(self._ctx("ar", cefr="A0"))
        self.assertIn("Reply primarily in Arabic", prompt)
        self.assertIn("English target", prompt)

    def test_arabic_pref_beginner_a1_gets_arabic_primary(self):
        prompt = _system_prompt(self._ctx("ar", cefr="A1"))
        self.assertIn("Reply primarily in Arabic", prompt)

    def test_arabic_pref_b1_gets_english_primary(self):
        prompt = _system_prompt(self._ctx("ar", cefr="B1"))
        # The B1 student's UI is Arabic but the AI replies in English —
        # short Arabic glosses are allowed when needed.
        self.assertNotIn("Reply primarily in Arabic", prompt)
        self.assertIn("Reply PRIMARILY in English", prompt)

    def test_arabic_pref_a2_gets_english_primary(self):
        prompt = _system_prompt(self._ctx("ar", cefr="A2"))
        self.assertIn("Reply PRIMARILY in English", prompt)

    def test_english_pref_stays_english(self):
        prompt = _system_prompt(self._ctx("en"))
        self.assertIn("Reply in English", prompt)
        self.assertNotIn("Reply primarily in Arabic", prompt)

    def test_voice_brevity_rule_still_applies_in_either_language(self):
        for lang in ("ar", "en"):
            prompt = _system_prompt(self._ctx(lang), voice=True)
            self.assertIn("Voice mode is ON", prompt)
            self.assertIn("at most 2 short sentences", prompt)
