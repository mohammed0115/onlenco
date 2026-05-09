"""Multinomial Naive Bayes — predicts the most likely next error type for a
student given their recent error history.

Pure-Python (no numpy/sklearn) so the Docker image stays lean. The
classifier is fit on UserError rows: features = (skill_id, grammar_topic_id),
class = error_type. With Laplace smoothing it stays well-behaved on tiny
training sets.

Public surface:
    fit(user) → NaiveBayesPredictor
    predictor.predict_top(features, k=3) → list[(error_type, log_prob)]
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Iterable, Tuple

from learning_core.models import UserError


class NaiveBayesPredictor:
    """Lightweight multinomial NB with Laplace smoothing."""

    def __init__(self):
        self.class_counts: Counter = Counter()
        self.feature_counts: dict = defaultdict(Counter)  # class → feature → count
        self.total_features_per_class: Counter = Counter()
        self.vocab: set = set()

    def fit(self, samples: Iterable[Tuple[str, dict]]) -> "NaiveBayesPredictor":
        """Train from `(class_label, {feature_name: feature_value})` pairs."""
        for cls, features in samples:
            self.class_counts[cls] += 1
            for k, v in (features or {}).items():
                token = f"{k}={v}"
                self.feature_counts[cls][token] += 1
                self.total_features_per_class[cls] += 1
                self.vocab.add(token)
        return self

    def predict_top(self, features: dict, k: int = 3) -> list[tuple[str, float]]:
        """Return top-k `(class, log_prob)` ranked by log-likelihood."""
        if not self.class_counts:
            return []
        total_docs = sum(self.class_counts.values())
        scores: dict[str, float] = {}
        vocab_size = max(len(self.vocab), 1)
        feature_tokens = [f"{k}={v}" for k, v in (features or {}).items()]
        for cls, count in self.class_counts.items():
            log_prob = math.log(count / total_docs)
            denom = self.total_features_per_class[cls] + vocab_size
            for tok in feature_tokens:
                num = self.feature_counts[cls].get(tok, 0) + 1
                log_prob += math.log(num / denom)
            scores[cls] = log_prob
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:k]


def fit_for_user(user) -> NaiveBayesPredictor:
    """Build a predictor from this user's UserError history."""
    samples = []
    qs = UserError.objects.filter(user=user).only(
        "error_type", "skill_id", "grammar_topic_id"
    )
    for err in qs:
        samples.append(
            (
                err.error_type,
                {
                    "skill": err.skill_id or "none",
                    "topic": err.grammar_topic_id or "none",
                },
            )
        )
    return NaiveBayesPredictor().fit(samples)


def fit_global() -> NaiveBayesPredictor:
    """Build a predictor from every user's UserError history."""
    samples = []
    for err in UserError.objects.all().only(
        "error_type", "skill_id", "grammar_topic_id"
    ):
        samples.append(
            (
                err.error_type,
                {
                    "skill": err.skill_id or "none",
                    "topic": err.grammar_topic_id or "none",
                },
            )
        )
    return NaiveBayesPredictor().fit(samples)
