"""Two-voice dialogue audio: each speaker gets a consistent gendered voice.

These exercise the planning helpers only (no provider call) so they run
without an API key.
"""
from django.test import TestCase, override_settings

from courses.services import media_generation_service as svc


class DialogueVoicePlanTests(TestCase):
    @override_settings(AI_TTS_FEMALE_VOICE="nova", AI_TTS_MALE_VOICE="onyx")
    def test_known_names_map_to_gendered_voices(self):
        text = "Salma: Hello, how are you?\nKareem: I am fine, thank you."
        plan = svc.build_dialogue_voice_plan(text)
        self.assertEqual(plan[0][0], "nova")   # Salma -> female
        self.assertEqual(plan[1][0], "onyx")   # Kareem -> male
        self.assertEqual(plan[0][1], "Hello, how are you?")

    @override_settings(AI_TTS_FEMALE_VOICE="nova", AI_TTS_MALE_VOICE="onyx")
    def test_same_speaker_keeps_one_voice(self):
        text = "Layla: Good morning.\nOmar: Good morning.\nLayla: Nice day!"
        plan = svc.build_dialogue_voice_plan(text)
        self.assertEqual(plan[0][0], plan[2][0])  # both Layla lines same voice
        self.assertNotEqual(plan[0][0], plan[1][0])  # Layla != Omar

    @override_settings(AI_TTS_FEMALE_VOICE="nova", AI_TTS_MALE_VOICE="onyx")
    def test_unknown_speakers_alternate_male_female(self):
        text = "Zorp: Hi there.\nBlee: Hello back."
        plan = svc.build_dialogue_voice_plan(text)
        self.assertNotEqual(plan[0][0], plan[1][0])
        self.assertIn(plan[0][0], {"nova", "onyx"})

    def test_narration_uses_default_voice(self):
        text = "The two friends met at the market.\nSalma: Hello!"
        plan = svc.build_dialogue_voice_plan(text, narration_voice="alloy")
        self.assertEqual(plan[0][0], "alloy")   # narration line

    def test_parse_dialogue_turns(self):
        turns = svc.parse_dialogue_turns("Salma: Hi.\nKareem: Hello.\nA narration line.")
        self.assertEqual(turns[0], ("Salma", "Hi."))
        self.assertEqual(turns[1], ("Kareem", "Hello."))
        self.assertEqual(turns[2], ("", "A narration line."))


class SentencePauseTests(TestCase):
    def test_sentences_get_line_breaks(self):
        out = svc.add_sentence_pauses("Hello there. How are you? Fine!")
        self.assertIn("Hello there.\n\nHow are you?", out)
