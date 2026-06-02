"""Group D — STT / TTS / realtime migration (Prompt 12A.1)."""
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client

from tutor.services import tts

from .helpers import FakeResponse, make_user


@override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True)
class AudioMigrationTests(TestCase):
    def test_stt_logs_usage(self):
        resp = FakeResponse(json_data={"text": "hi", "duration": 9.2})
        with mock.patch.object(ai_client.requests, "post", return_value=resp):
            ai_client.transcribe_audio(b"bytes", feature=C.FEATURE_STT, model="whisper-1")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.feature, C.FEATURE_STT)
        self.assertEqual(log.audio_input_seconds, 9)

    def test_tts_logs_usage(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(content=b"mp3-bytes")):
            out = tts.synthesize("Hello there, how are you today?")
        self.assertTrue(out["audio_b64"])
        log = AIUsageLog.objects.get()
        self.assertEqual(log.feature, C.FEATURE_TTS)
        self.assertGreater(log.audio_output_seconds, 0)

    def test_realtime_minutes_logged_if_present(self):
        user = make_user("rt")
        ai_client.log_realtime_session_start(user=user, role=C.ROLE_STUDENT,
                                             session_id="tutor_session:1")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.feature, C.FEATURE_AI_TUTOR)
        self.assertTrue(log.metadata.get("realtime_reconcile_required"))
        self.assertEqual(log.metadata.get("event"), "realtime_session_start")

    def test_audio_cost_calculation_from_pricing(self):
        # whisper-1 seeded at $0.006/min audio input → 60s = $0.006.
        resp = FakeResponse(json_data={"text": "x", "duration": 60})
        with mock.patch.object(ai_client.requests, "post", return_value=resp):
            ai_client.transcribe_audio(b"bytes", feature=C.FEATURE_STT, model="whisper-1")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.estimated_cost_usd, Decimal("0.006000"))

    def test_audio_failure_logged(self):
        with mock.patch.object(ai_client.requests, "post",
                               side_effect=RuntimeError("net")):
            with self.assertRaises(RuntimeError):
                ai_client.transcribe_audio(b"bytes", feature=C.FEATURE_STT, model="whisper-1")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.status, C.STATUS_FAILED)
