"""Audit fixes #15 (voice brevity) + #24 (weakness recompute on tutor turn).

These behaviours used to be silent: voice users got long text-style
replies, and weakness scores stayed stale until a quiz/exam refreshed
them. Both gaps are now wired into `tutor.services.chat`.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from learning_core.models import Skill, UserError, UserWeakness
from tutor.models import TutorConversation
from tutor.services import chat
from tutor.services._chat import _system_prompt
from tutor.services.context_builder import build_tutor_context

User = get_user_model()


class VoiceModeBrevityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vm", password="pw")

    def test_voice_off_omits_brevity_rule(self):
        ctx = build_tutor_context(self.user)
        prompt = _system_prompt(ctx, voice=False)
        self.assertNotIn("Voice mode is ON", prompt)

    def test_voice_on_adds_brevity_rule(self):
        ctx = build_tutor_context(self.user)
        prompt = _system_prompt(ctx, voice=True)
        self.assertIn("Voice mode is ON", prompt)
        self.assertIn("at most 2 short sentences", prompt)

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_chat_passes_voice_flag_into_system_prompt(self):
        from tutor.services import _chat as chat_mod

        captured = {}

        class R:
            status_code = 200
            def raise_for_status(self_inner): pass
            def json(self_inner):
                return {"choices": [{"message": {"content": "Sure! What now?"}}]}

        def fake_post(url, **kwargs):
            # First call only — post-chat hooks (analyze_text) make
            # their own requests.post calls in TUTOR_HOOKS_SYNC tests.
            if "payload" not in captured:
                captured["payload"] = kwargs.get("json")
            return R()

        conv = TutorConversation.objects.create(user=self.user, topic="travel")
        with patch.object(chat_mod.requests, "post", side_effect=fake_post):
            chat(conv, "Hello", voice=True)

        sys_msg = captured["payload"]["messages"][0]
        self.assertEqual(sys_msg["role"], "system")
        self.assertIn("Voice mode is ON", sys_msg["content"])

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_chat_default_is_text_mode(self):
        from tutor.services import _chat as chat_mod

        captured = {}

        class R:
            status_code = 200
            def raise_for_status(self_inner): pass
            def json(self_inner):
                return {"choices": [{"message": {"content": "Hi"}}]}

        def fake_post(url, **kwargs):
            # First call only — post-chat hooks (analyze_text) make
            # their own requests.post calls in TUTOR_HOOKS_SYNC tests.
            if "payload" not in captured:
                captured["payload"] = kwargs.get("json")
            return R()

        conv = TutorConversation.objects.create(user=self.user)
        with patch.object(chat_mod.requests, "post", side_effect=fake_post):
            chat(conv, "Hello")  # voice not passed → defaults to False

        sys_msg = captured["payload"]["messages"][0]
        self.assertNotIn("Voice mode is ON", sys_msg["content"])


class WeaknessRecomputeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wr", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user, topic="grammar")

    @override_settings(AI_API_KEY="")
    def test_chat_calls_weakness_engine_after_each_turn(self):
        from tutor.services import _chat as chat_mod

        with patch(
            "learning_core.services.weakness_engine.update_user_weaknesses"
        ) as mock_update:
            chat(self.conv, "I goes to school")
            self.assertGreaterEqual(mock_update.call_count, 1)
            mock_update.assert_called_with(self.user)

    @override_settings(AI_API_KEY="")
    def test_chat_swallows_weakness_engine_failure(self):
        # Recompute is best-effort: a crash in weakness engine must not
        # break the chat flow.
        with patch(
            "learning_core.services.weakness_engine.update_user_weaknesses",
            side_effect=RuntimeError("boom"),
        ):
            reply = chat(self.conv, "hello")
        self.assertTrue(reply)  # still got a reply

    @override_settings(AI_API_KEY="")
    def test_user_errors_still_persisted_when_weakness_engine_crashes(self):
        with patch(
            "learning_core.services.weakness_engine.update_user_weaknesses",
            side_effect=RuntimeError("boom"),
        ):
            chat(self.conv, "she go to market yesterday")
        self.assertGreaterEqual(
            UserError.objects.filter(user=self.user, source_type="tutor").count(), 1
        )
