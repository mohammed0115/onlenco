"""Retired-voice safety net.

OpenAI's GA Realtime API retired ``nova`` / ``onyx`` / ``fable`` — those
return HTTP 400 ``invalid_value`` on ``/v1/realtime/client_secrets``.
``coerce_supported_voice`` maps them to GA-supported equivalents so
existing user preferences keep working without manual re-selection.
"""
from django.test import TestCase

from tutor.services.realtime_session import (
    REALTIME_GA_VOICES,
    RETIRED_VOICE_FALLBACKS,
    coerce_supported_voice,
)


class VoiceCoercionTests(TestCase):
    def test_ga_voices_pass_through(self):
        for voice in REALTIME_GA_VOICES:
            self.assertEqual(coerce_supported_voice(voice), voice)

    def test_retired_voices_remap(self):
        for retired, expected in RETIRED_VOICE_FALLBACKS.items():
            self.assertEqual(coerce_supported_voice(retired), expected)
            # And the target is itself a GA-supported voice.
            self.assertIn(expected, REALTIME_GA_VOICES)

    def test_unknown_voice_falls_back_to_alloy(self):
        self.assertEqual(coerce_supported_voice("totally-not-a-voice"), "alloy")

    def test_empty_falls_back_to_alloy(self):
        self.assertEqual(coerce_supported_voice(""), "alloy")
        self.assertEqual(coerce_supported_voice(None), "alloy")  # type: ignore[arg-type]

    def test_case_insensitive(self):
        self.assertEqual(coerce_supported_voice("ALLOY"), "alloy")
        self.assertEqual(coerce_supported_voice("Nova"), "shimmer")
        self.assertEqual(coerce_supported_voice("  alloy  "), "alloy")


class VoiceProfileSeedRemapTests(TestCase):
    """The data migration in 0009 remapped retired voices in DB."""

    def test_no_voice_profile_uses_retired_id(self):
        from subscriptions.models import VoiceProfile
        retired = set(RETIRED_VOICE_FALLBACKS.keys())
        used = set(VoiceProfile.objects.values_list("provider_voice_id", flat=True))
        self.assertFalse(used & retired, f"Retired voices in DB: {used & retired}")
