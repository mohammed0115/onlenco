from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    GrammarTopic,
    LearningRecommendation,
    Skill,
    SkillMastery,
    StudentLearningProfile,
    UserError,
    UserWeakness,
)

User = get_user_model()


class LearningCoreModelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="pw"
        )
        self.skill = Skill.objects.create(
            name="Past Simple usage", category="grammar", cefr_level="A2"
        )
        self.topic = GrammarTopic.objects.create(
            name="Past Simple", slug="past-simple", cefr_level="A2"
        )
        self.topic.related_skills.add(self.skill)

    def test_skill_str_and_unique(self):
        self.assertIn("Grammar", str(self.skill))
        with self.assertRaises(IntegrityError):
            Skill.objects.create(
                name="Past Simple usage", category="grammar", cefr_level="A2"
            )

    def test_grammar_topic_unique_slug(self):
        with self.assertRaises(IntegrityError):
            GrammarTopic.objects.create(
                name="Other", slug="past-simple", cefr_level="A2"
            )

    def test_student_learning_profile_one_per_user(self):
        profile = StudentLearningProfile.objects.create(
            user=self.user, current_cefr_level="A2", theta_score=0.5
        )
        self.assertEqual(profile.user, self.user)
        self.assertEqual(self.user.learning_profile, profile)
        with self.assertRaises(IntegrityError):
            StudentLearningProfile.objects.create(user=self.user)

    def test_skill_mastery_unique_per_user_skill(self):
        SkillMastery.objects.create(user=self.user, skill=self.skill, mastery_score=10)
        with self.assertRaises(IntegrityError):
            SkillMastery.objects.create(user=self.user, skill=self.skill)

    def test_user_error_creation_links_skill_and_topic(self):
        err = UserError.objects.create(
            user=self.user,
            source_type="quiz",
            original_text="I goes home",
            corrected_text="I go home",
            error_type="grammar",
            grammar_topic=self.topic,
            skill=self.skill,
            severity=4,
            explanation="Subject-verb agreement.",
            ai_confidence=0.9,
        )
        self.assertEqual(err.user.user_errors.count(), 1)
        self.assertEqual(err.skill, self.skill)
        self.assertEqual(err.grammar_topic, self.topic)

    def test_user_weakness_unique_per_user_skill_topic(self):
        UserWeakness.objects.create(
            user=self.user,
            skill=self.skill,
            grammar_topic=self.topic,
            weakness_score=42.0,
            priority_score=12.3,
        )
        with self.assertRaises(IntegrityError):
            UserWeakness.objects.create(
                user=self.user, skill=self.skill, grammar_topic=self.topic
            )

    def test_adaptive_exercise_and_attempt(self):
        ex = AdaptiveExercise.objects.create(
            topic=self.topic,
            skill=self.skill,
            cefr_level="A2",
            difficulty_score=0.4,
            question_type="multiple_choice",
            question="She ___ to school yesterday.",
            options=["go", "went", "gone", "goes"],
            correct_answer="went",
            explanation="Past simple of 'go' is 'went'.",
            generated_by_ai=False,
        )
        attempt = ExerciseAttempt.objects.create(
            user=self.user,
            exercise=ex,
            user_answer="went",
            is_correct=True,
            score=1.0,
            time_spent_seconds=8,
        )
        self.assertTrue(attempt.is_correct)
        self.assertEqual(ex.attempts.count(), 1)

    def test_learning_recommendation(self):
        rec = LearningRecommendation.objects.create(
            user=self.user,
            recommendation_type="practice_skill",
            title="Practice Past Simple",
            description="3 short exercises on irregular verbs.",
            priority=8.0,
            related_skill=self.skill,
        )
        self.assertEqual(self.user.learning_recommendations.first(), rec)
        self.assertEqual(rec.status, "pending")
