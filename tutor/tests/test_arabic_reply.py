"""Arabic-pref students get Arabic-primary replies, English-pref stay English."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from tutor.services._chat import _system_prompt
from tutor.services.context_builder import build_tutor_context

User = get_user_model()


class ArabicReplyPromptTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ar@x.com", password="pw")

    def _ctx(self, lang):
        self.user.profile.preferred_language = lang
        self.user.profile.save(update_fields=["preferred_language"])
        return build_tutor_context(self.user)

    def test_arabic_pref_gets_arabic_primary_rule(self):
        prompt = _system_prompt(self._ctx("ar"))
        self.assertIn("Reply primarily in Arabic", prompt)
        self.assertIn("English target", prompt)

    def test_english_pref_stays_english(self):
        prompt = _system_prompt(self._ctx("en"))
        self.assertIn("Reply in English", prompt)
        self.assertNotIn("Reply primarily in Arabic", prompt)

    def test_voice_brevity_rule_still_applies_in_either_language(self):
        for lang in ("ar", "en"):
            prompt = _system_prompt(self._ctx(lang), voice=True)
            self.assertIn("Voice mode is ON", prompt)
            self.assertIn("at most 2 short sentences", prompt)
