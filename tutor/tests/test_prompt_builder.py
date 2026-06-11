"""Prompt 17.5 — language policy + technical-token sanitisation for AI Tutor."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from tutor.models import TutorConversation
from tutor.services import prompt_builder as pb

User = get_user_model()


class LanguagePolicyTests(TestCase):
    def test_a0_a1_use_arabic_support_and_short(self):
        for lvl in ("A0", "A1"):
            pol = pb.get_language_policy(lvl)
            self.assertTrue(pol["arabic_support"])
            self.assertTrue(pol["keep_short"])
            self.assertEqual(pol["reply_language"], "ar_primary")
            self.assertTrue(pb.should_use_arabic_support(lvl))
            self.assertTrue(pb.should_keep_reply_short(lvl))

    def test_a2_simple_english_with_arabic_gloss(self):
        pol = pb.get_language_policy("A2")
        self.assertEqual(pol["reply_language"], "en_with_ar_gloss")
        self.assertTrue(pol["arabic_support"])

    def test_b1_plus_mostly_english(self):
        for lvl in ("B1", "B2", "C1"):
            pol = pb.get_language_policy(lvl)
            self.assertEqual(pol["reply_language"], "en")
            self.assertFalse(pol["arabic_support"])
            self.assertFalse(pol["keep_short"])


class SanitizeOutputTests(TestCase):
    def test_underscores_are_removed(self):
        out = pb.sanitize_tutor_output_text("Great! Try user_answer_text now.")
        self.assertNotIn("_", out)

    def test_json_is_stripped(self):
        out = pb.sanitize_tutor_output_text('Result: {"score": 5, "level": "A1"} done.')
        self.assertNotIn("{", out)
        self.assertNotIn('"score"', out)

    def test_filename_is_stripped(self):
        out = pb.sanitize_tutor_output_text("Saved to recording.webm successfully.")
        self.assertNotIn("recording.webm", out)
        self.assertNotIn(".webm", out)

    def test_provider_and_model_names_removed(self):
        out = pb.sanitize_tutor_output_text("I used OpenAI gpt-4o and whisper-1 to reply.")
        low = out.lower()
        for token in ("openai", "gpt-4o", "whisper"):
            self.assertNotIn(token, low)

    def test_uuid_and_code_fence_removed(self):
        out = pb.sanitize_tutor_output_text(
            "id 550e8400-e29b-41d4-a716-446655440000 ```print(x)``` ok"
        )
        self.assertNotIn("550e8400", out)
        self.assertNotIn("print(x)", out)

    def test_empty_after_clean_uses_level_fallback(self):
        a1 = pb.sanitize_tutor_output_text("____", level="A1")
        self.assertEqual(a1, "حاول مرة أخرى بجملة قصيرة.")
        b1 = pb.sanitize_tutor_output_text("____", level="B1")
        self.assertEqual(b1, "Please try again with a short sentence.")


class OpeningInstructionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pb@x.com", password="pw")
        self.user.profile.cefr_level = "A1"
        self.user.profile.save()

    def test_call_opening_keeps_tutor_first_contract(self):
        text = pb.build_opening_instruction(self.user, pb.MODE_REGULAR_AI_TUTOR_CALL)
        self.assertIn("Do not wait for the student", text)
        # No technical tokens in our own controlled copy.
        for bad in ("_", "{", "json", "gpt"):
            self.assertNotIn(bad, text.lower())

    def test_placement_opening_is_non_empty(self):
        text = pb.build_opening_instruction(self.user, pb.MODE_PLACEMENT_SPEAKING_CALL)
        self.assertIn("placement", text.lower())
        self.assertIn("Do not wait for the student", text)

    def test_message_mode_has_no_opening(self):
        self.assertEqual(
            pb.build_opening_instruction(self.user, pb.MODE_REGULAR_AI_TUTOR_MESSAGE), ""
        )


class SystemPromptWiringTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pbsp@x.com", password="pw")
        self.user.profile.cefr_level = "A1"
        self.user.profile.preferred_language = "ar"
        self.user.profile.save()

    def test_message_system_prompt_builds(self):
        prompt = pb.build_tutor_system_prompt(self.user, pb.MODE_REGULAR_AI_TUTOR_MESSAGE)
        self.assertIsInstance(prompt, str)
        self.assertTrue(len(prompt) > 0)


@override_settings(AI_API_KEY="test-key")
class ChatReplySanitizedTests(TestCase):
    """The reply returned by chat() (text + voice) passes through the sanitiser."""

    def setUp(self):
        self.user = User.objects.create_user(username="pbchat@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user)

    def _fake_reply(self, content):
        return {"choices": [{"message": {"content": content}}]}

    def test_text_reply_is_sanitized(self):
        from tutor.services._chat import chat
        with patch("tutor.services._chat.fire_post_chat_hooks"), \
             patch("ai_usage.services.ai_client.chat",
                   return_value=self._fake_reply("Good! Try user_answer now.")):
            reply = chat(self.conv, "hi", voice=False)
        self.assertNotIn("_", reply)

    def test_voice_reply_is_sanitized(self):
        from tutor.services._chat import chat
        with patch("tutor.services._chat.fire_post_chat_hooks"), \
             patch("ai_usage.services.ai_client.chat",
                   return_value=self._fake_reply('Reply {"k": 1} recording.mp4 done.')):
            reply = chat(self.conv, "hi", voice=True)
        self.assertNotIn("{", reply)
        self.assertNotIn(".mp4", reply)
