"""Group C — Placement written + speaking migration (Prompt 12A.1)."""
import json
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client

from placement.services import _assessor, stt

from .helpers import FakeResponse


def _tool_call_json():
    args = json.dumps({"level": "A2", "written_score": 60,
                       "speaking_score": 55, "feedback": "Good effort."})
    return {
        "choices": [{"message": {"tool_calls": [
            {"function": {"name": "assess_level", "arguments": args}}]}}],
        "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
    }


SAMPLE_ANSWERS = {"q1": "I go to school every day.", "q2": "Yesterday I went home."}


@override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True)
class PlacementMigrationTests(TestCase):
    def test_placement_written_logs_usage(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=_tool_call_json())):
            result = _assessor.assess(SAMPLE_ANSWERS)
        self.assertEqual(result["level"], "A2")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.feature, C.FEATURE_PLACEMENT_WRITTEN)
        self.assertEqual(log.status, C.STATUS_SUCCESS)
        self.assertEqual(log.input_tokens, 80)

    def test_placement_speaking_logs_usage(self):
        audio = SimpleUploadedFile("a.webm", b"fakeaudio", content_type="audio/webm")
        resp = FakeResponse(json_data={"text": "hello world", "duration": 7.6})
        with mock.patch.object(ai_client.requests, "post", return_value=resp):
            out = stt.transcribe(audio)
        self.assertEqual(out["transcript"], "hello world")
        self.assertEqual(out["duration_seconds"], 8)
        log = AIUsageLog.objects.get()
        self.assertEqual(log.feature, C.FEATURE_PLACEMENT_SPEAKING)
        self.assertEqual(log.audio_input_seconds, 8)
        # Placement speaking does NOT consume AI-Tutor minutes (onboarding).
        self.assertEqual(log.ai_minutes_used, 0)

    def test_placement_ai_failure_logged(self):
        with mock.patch.object(ai_client.requests, "post",
                               side_effect=RuntimeError("boom")):
            result = _assessor.assess(SAMPLE_ANSWERS)
        # Heuristic fallback still returns a usable result…
        self.assertIn("feedback", result)
        # …and the failure is logged.
        log = AIUsageLog.objects.get()
        self.assertEqual(log.feature, C.FEATURE_PLACEMENT_WRITTEN)
        self.assertEqual(log.status, C.STATUS_FAILED)
