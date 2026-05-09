from django.contrib.auth import get_user_model
from django.test import TestCase

from learning_core.models import (
    Skill,
    StudentLearningProfile,
    UserError,
)
from learning_core.services.ml.kmeans import _build_feature_vectors, kmeans
from learning_core.services.ml.naive_bayes import NaiveBayesPredictor, fit_for_user

User = get_user_model()


class NaiveBayesTests(TestCase):
    def test_predicts_dominant_class_on_seen_features(self):
        nb = NaiveBayesPredictor().fit([
            ("grammar", {"skill": 1, "topic": 5}),
            ("grammar", {"skill": 1, "topic": 5}),
            ("grammar", {"skill": 1, "topic": 5}),
            ("vocabulary", {"skill": 2, "topic": 9}),
        ])
        top = nb.predict_top({"skill": 1, "topic": 5}, k=1)
        self.assertEqual(top[0][0], "grammar")

    def test_handles_unseen_features_with_smoothing(self):
        nb = NaiveBayesPredictor().fit([
            ("a", {"x": 1}),
            ("b", {"x": 2}),
        ])
        top = nb.predict_top({"x": 99}, k=2)
        # Should still return both classes ranked by prior; no crash.
        self.assertEqual({c for c, _ in top}, {"a", "b"})

    def test_empty_predictor_returns_empty(self):
        nb = NaiveBayesPredictor()
        self.assertEqual(nb.predict_top({"x": 1}), [])

    def test_fit_for_user_pulls_real_errors(self):
        u = User.objects.create_user(username="nb@x.com", email="nb@x.com", password="pw")
        skill = Skill.objects.create(name="reading", category="reading")
        for _ in range(3):
            UserError.objects.create(
                user=u, source_type="quiz", error_type="grammar",
                skill=skill, severity=5, ai_confidence=0.0,
            )
        UserError.objects.create(
            user=u, source_type="quiz", error_type="vocabulary",
            skill=skill, severity=3, ai_confidence=0.0,
        )
        nb = fit_for_user(u)
        top = nb.predict_top({"skill": skill.id, "topic": "none"}, k=2)
        self.assertEqual(top[0][0], "grammar")


class KMeansTests(TestCase):
    def test_handles_empty_input(self):
        self.assertEqual(kmeans({}, k=3), {})

    def test_produces_at_most_k_clusters(self):
        vectors = {1: [0, 0, 0, 0, 0, 0],
                   2: [1, 1, 1, 1, 1, 1],
                   3: [0, 0, 0, 0, 0, 0],
                   4: [1, 1, 1, 1, 1, 1]}
        out = kmeans(vectors, k=2, seed=1)
        self.assertEqual(len(out), 4)
        self.assertLessEqual(len(set(out.values())), 2)

    def test_clamps_k_to_n(self):
        out = kmeans({1: [0, 0, 0, 0, 0, 0], 2: [1, 1, 1, 1, 1, 1]}, k=10)
        self.assertEqual(len(out), 2)
        self.assertLessEqual(len(set(out.values())), 2)

    def test_build_feature_vectors_uses_profile(self):
        u = User.objects.create_user(username="km@x.com", email="km@x.com", password="pw")
        StudentLearningProfile.objects.create(user=u, theta_score=0.5, learning_speed=1.2)
        vecs = _build_feature_vectors()
        self.assertIn(u.id, vecs)
        self.assertEqual(len(vecs[u.id]), 6)
        self.assertAlmostEqual(vecs[u.id][0], 0.5)
