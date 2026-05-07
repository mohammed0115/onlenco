from unittest.mock import patch

from django.test import TestCase, override_settings

from tutor.services import synthesize


class TTSTests(TestCase):
    @override_settings(AI_API_KEY="")
    def test_no_api_key_returns_empty_payload(self):
        result = synthesize("Hello there")
        self.assertEqual(result, {"audio_b64": "", "format": "", "voice": ""})

    @override_settings(AI_API_KEY="")
    def test_empty_text_returns_empty(self):
        result = synthesize("")
        self.assertEqual(result["audio_b64"], "")

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m", AI_TTS_MODEL="tts-1", AI_TTS_VOICE="alloy")
    def test_success_returns_base64(self):
        from tutor.services import tts as tts_module

        class R:
            status_code = 200
            content = b"fake-mp3-bytes"

            def raise_for_status(self_inner):
                pass

        with patch.object(tts_module.requests, "post", return_value=R()):
            result = synthesize("Hello")
        self.assertNotEqual(result["audio_b64"], "")
        self.assertEqual(result["format"], "mp3")

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x")
    def test_failure_returns_empty(self):
        from tutor.services import tts as tts_module

        with patch.object(tts_module.requests, "post", side_effect=RuntimeError("boom")):
            result = synthesize("Hello")
        self.assertEqual(result["audio_b64"], "")
