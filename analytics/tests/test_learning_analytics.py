from django.contrib.auth import get_user_model
from django.test import TestCase

from analytics.services_learning import compute_learning_metrics
from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    GrammarTopic,
    Skill,
    SkillMastery,
    StudentLearningProfile,
    UserError,
    UserWeakness,
)

User = get_user_model()


class LearningAnalyticsTests(TestCase):
    def test_empty_dataset_returns_zeros(self):
        m = compute_learning_metrics(days=30)
        self.assertEqual(m["active_learners"], 0)
        self.assertEqual(m["exercise_attempts_total"], 0)
        self.assertEqual(m["exercise_success_rate"], 0.0)
        self.assertEqual(m["cefr_distribution"], [])
        self.assertEqual(m["top_weaknesses"], [])

    def test_metrics_with_data(self):
        u = User.objects.create_user(username="m", password="pw")
        skill = Skill.objects.create(name="Reading core", category="reading", cefr_level="A2")
        topic = GrammarTopic.objects.create(name="Past Simple", slug="past-simple", cefr_level="A2")
        StudentLearningProfile.objects.create(user=u, current_cefr_level="A2", theta_score=0.0)
        SkillMastery.objects.create(user=u, skill=skill, mastery_score=30)
        ex = AdaptiveExercise.objects.create(
            skill=skill,
            cefr_level="A2",
            difficulty_score=0.4,
            question_type="multiple_choice",
            question="x",
            options=["a"],
            correct_answer="a",
            generated_by_ai=True,
        )
        ExerciseAttempt.objects.create(user=u, exercise=ex, is_correct=True, score=1.0)
        ExerciseAttempt.objects.create(user=u, exercise=ex, is_correct=False, score=0.0)
        UserError.objects.create(user=u, source_type="quiz", error_type="grammar", severity=5, skill=skill)
        UserWeakness.objects.create(
            user=u, skill=skill, grammar_topic=topic, weakness_score=40, priority_score=40, status="active"
        )

        m = compute_learning_metrics(days=30)
        self.assertEqual(m["active_learners"], 1)
        self.assertEqual(m["exercise_attempts_total"], 2)
        self.assertEqual(m["exercise_success_rate"], 50.0)
        self.assertGreaterEqual(m["exercises_generated_by_ai"], 1)
        self.assertGreaterEqual(len(m["cefr_distribution"]), 1)
        self.assertGreaterEqual(len(m["top_weaknesses"]), 1)
        self.assertGreaterEqual(len(m["error_type_breakdown"]), 1)

    def test_cefr_filter_applied(self):
        u = User.objects.create_user(username="z", password="pw")
        StudentLearningProfile.objects.create(user=u, current_cefr_level="A1", theta_score=-1.0)
        m = compute_learning_metrics(days=30, cefr_level="A2")
        self.assertEqual(m["filters"]["cefr_level"], "A2")
