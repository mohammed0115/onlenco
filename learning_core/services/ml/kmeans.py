"""K-Means learner clustering — groups students by adaptive-learning state.

Pure-Python (no numpy/sklearn) so the deploy image stays lean. We cluster
on a small fixed-size feature vector built from
`StudentLearningProfile` + aggregated mastery + error counts:

    [theta_score, learning_speed, confidence_score,
     avg_mastery, error_count_norm, lessons_done_norm]

Use cases:
- group similar learners for cohort analytics
- find peers for collaborative recommendations
- identify outliers that may need teacher attention

Public surface:
    cluster_users(k=4) → dict[user_id, cluster_index]
"""
from __future__ import annotations

import math
import random
from typing import Sequence

from django.db.models import Avg, Count

from learning_core.models import (
    SkillMastery,
    StudentLearningProfile,
    UserError,
)
from lessons.models import LessonProgress


def _euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _build_feature_vectors() -> dict:
    """{user_id: feature_vec}. Skips users with no learning profile."""
    out: dict[int, list[float]] = {}
    profiles = StudentLearningProfile.objects.select_related("user").all()
    if not profiles:
        return out

    # Mastery + error + lesson aggregates, normalised after the loop.
    user_ids = [p.user_id for p in profiles]
    mastery = dict(
        SkillMastery.objects.filter(user_id__in=user_ids)
        .values_list("user_id")
        .annotate(avg=Avg("mastery_score"))
        .values_list("user_id", "avg")
    )
    errors = dict(
        UserError.objects.filter(user_id__in=user_ids)
        .values_list("user_id")
        .annotate(c=Count("id"))
        .values_list("user_id", "c")
    )
    lessons_done = dict(
        LessonProgress.objects.filter(
            user_id__in=user_ids, completed_at__isnull=False
        )
        .values_list("user_id")
        .annotate(c=Count("id"))
        .values_list("user_id", "c")
    )

    max_errors = max(errors.values(), default=1) or 1
    max_lessons = max(lessons_done.values(), default=1) or 1

    for p in profiles:
        out[p.user_id] = [
            float(p.theta_score or 0.0),
            float(p.learning_speed or 1.0),
            float(p.confidence_score or 0.0),
            float(mastery.get(p.user_id) or 0.0) / 100.0,
            float(errors.get(p.user_id, 0)) / max_errors,
            float(lessons_done.get(p.user_id, 0)) / max_lessons,
        ]
    return out


def kmeans(vectors: dict, k: int = 4, *, max_iter: int = 100, seed: int = 42) -> dict:
    """Run k-means and return {user_id: cluster_index}.

    Robust to k > len(vectors) (clamps), and to all-equal vectors (one
    cluster wins). Distance function: Euclidean.
    """
    if not vectors:
        return {}
    items = list(vectors.items())
    points = [v for _, v in items]
    n = len(points)
    k = max(1, min(k, n))

    rng = random.Random(seed)
    # k-means++ light: first centroid random, then favour distant ones.
    centroids = [points[rng.randrange(n)]]
    while len(centroids) < k:
        dists = [
            min(_euclidean(p, c) ** 2 for c in centroids)
            for p in points
        ]
        total = sum(dists) or 1.0
        r = rng.random() * total
        cum = 0.0
        for p, d in zip(points, dists):
            cum += d
            if cum >= r:
                centroids.append(p)
                break

    assignments = [0] * n
    for _ in range(max_iter):
        # Assign
        new_assign = []
        for p in points:
            distances = [_euclidean(p, c) for c in centroids]
            new_assign.append(distances.index(min(distances)))
        if new_assign == assignments:
            break
        assignments = new_assign

        # Recompute centroids
        for ci in range(k):
            members = [p for p, a in zip(points, assignments) if a == ci]
            if not members:
                continue
            dim = len(members[0])
            centroids[ci] = [
                sum(m[d] for m in members) / len(members)
                for d in range(dim)
            ]

    return {uid: assignments[i] for i, (uid, _) in enumerate(items)}


def cluster_users(k: int = 4) -> dict:
    """Convenience wrapper. Returns {user_id: cluster_idx}."""
    vectors = _build_feature_vectors()
    return kmeans(vectors, k=k)
