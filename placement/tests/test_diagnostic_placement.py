from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from learning_core.models import (
    Skill,
    SkillMastery,
    StudentLearningProfile,
    UserError,
    UserWeakness,
)
from placement.services.diagnostic_engine import build_diagnostic_profile
from placement.services import assess

User = get_user_model()


SAMPLE_ANSWERS = {
    "q1": "goes",
    "q2": "If I had known, I would have helped.",
    "q3": "I likes football and i goes to the stadium with my friends every weekends.",
    "q4": "Yesterday I goed to the market and buyed some apples and breads.",
    "q5": (
        "Every morning i wake up at six and i drink tea then i goes to school. "
        "After school i plays football with friends and we have fun."
    ),
}


class DiagnosticEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dax", password="pw")
        Skill.objects.create(name="Reading core", category="reading", cefr_level="A2")
        Skill.objects.create(name="Writing core", category="writing", cefr_level="A2")
        Skill.objects.create(name="Grammar core", category="grammar", cefr_level="A2")

    @override_settings(AI_API_KEY="")  # forces heuristic fallback in assess()
    def test_new_user_placement_creates_full_diagnostic(self):
        result = build_diagnostic_profile(self.user, SAMPLE_ANSWERS)
        self.assertIn(result["cefr_level"], ["A0", "A1", "A2", "B1", "B2", "C1", "C2"])
        # Profile created and seeded
        profile = StudentLearningProfile.objects.get(user=self.user)
        self.assertEqual(profile.current_cefr_level, result["cefr_level"])
        # Skill masteries initialized
        self.assertGreaterEqual(SkillMastery.objects.filter(user=self.user).count(), 3)

    @override_settings(AI_API_KEY="")
    def test_errors_detected_from_free_form_answers(self):
        build_diagnostic_profile(self.user, SAMPLE_ANSWERS)
        # Heuristic should catch "i goes", "i likes" etc. as grammar errors
        self.assertGreaterEqual(
            UserError.objects.filter(user=self.user, source_type="placement").count(), 1
        )

    @override_settings(AI_API_KEY="")
    def test_existing_user_retake_updates_profile(self):
        StudentLearningProfile.objects.create(
            user=self.user, current_cefr_level="A0", theta_score=-2.5
        )
        result = build_diagnostic_profile(self.user, SAMPLE_ANSWERS)
        profile = StudentLearningProfile.objects.get(user=self.user)
        self.assertEqual(profile.current_cefr_level, result["cefr_level"])
        # theta is reseeded
        self.assertNotEqual(profile.theta_score, -2.5)

    @override_settings(AI_API_KEY="")
    def test_diagnostic_response_shape(self):
        result = build_diagnostic_profile(self.user, SAMPLE_ANSWERS)
        for key in (
            "cefr_level",
            "score",
            "written_score",
            "speaking_score",
            "grammar_strengths",
            "grammar_weaknesses",
            "vocabulary_level",
            "writing_quality",
            "speaking_transcript_quality",
            "errors_detected",
        ):
            self.assertIn(key, result)

    @override_settings(AI_API_KEY="")
    def test_engine_works_with_pre_supplied_assessment(self):
        # Force a known result
        canned = {
            "level": "B1",
            "written_score": 60,
            "speaking_score": 55,
            "feedback": "ok",
        }
        result = build_diagnostic_profile(self.user, SAMPLE_ANSWERS, assessment=canned)
        self.assertEqual(result["cefr_level"], "B1")
        self.assertEqual(result["written_score"], 60)

    @override_settings(AI_API_KEY="")
    def test_dynamic_answers_feed_all_written_text_to_error_analysis(self):
        canned = {
            "level": "B1",
            "written_score": 60,
            "speaking_score": 55,
            "feedback": "ok",
        }
        dynamic_answers = {
            "mode": "dynamic",
            "items": [
                {
                    "section": "written",
                    "expected_answer_type": "short_text",
                    "answer": "First dynamic writing answer.",
                },
                {
                    "section": "written",
                    "expected_answer_type": "mcq",
                    "answer": "goes",
                },
                {
                    "section": "written",
                    "expected_answer_type": "paragraph",
                    "answer": "Fifth dynamic writing answer should be analyzed too.",
                },
                {
                    "section": "speaking",
                    "expected_answer_type": "voice",
                    "answer": "Speaking answer.",
                },
            ],
        }

        with patch("placement.services.diagnostic_engine.analyze_text") as mocked:
            build_diagnostic_profile(self.user, dynamic_answers, assessment=canned)

        analyzed_text = mocked.call_args.args[1]
        self.assertIn("First dynamic writing answer", analyzed_text)
        self.assertIn("Fifth dynamic writing answer", analyzed_text)
        self.assertNotIn("goes", analyzed_text)
