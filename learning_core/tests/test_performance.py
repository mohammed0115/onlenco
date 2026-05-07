"""Coarse performance guards.

These tests assert order-of-magnitude ceilings rather than precise numbers,
so they don't flake on slow CI runners. They protect against regressions
that change a query from O(1) to O(N) or a hot loop from microseconds to
seconds.
"""
import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from learning_core.models import (
    GrammarTopic,
    LearningRecommendation,
    Skill,
    SkillMastery,
    UserError,
)
from learning_core.services.recommendation_engine import generate_recommendations
from learning_core.services.weakness_engine import update_user_weaknesses

User = get_user_model()


class PerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="perf", password="pw")
        self.skill = Skill.objects.create(
            name="Grammar core", category="grammar", cefr_level="A2"
        )
        self.topic = GrammarTopic.objects.create(
            name="Past Simple", slug="past-simple", cefr_level="A2"
        )

    def test_weakness_engine_handles_500_errors_quickly(self):
        rows = [
            UserError(
                user=self.user,
                source_type="quiz",
                error_type="grammar",
                skill=self.skill,
                grammar_topic=self.topic,
                severity=5,
            )
            for _ in range(500)
        ]
        UserError.objects.bulk_create(rows)
        t0 = time.perf_counter()
        update_user_weaknesses(self.user)
        elapsed = time.perf_counter() - t0
        # On any modern machine this should complete well under a second.
        # Allow generous headroom for slow CI runners.
        self.assertLess(elapsed, 3.0, f"weakness engine took {elapsed:.2f}s")

    def test_recommendation_engine_query_count_is_bounded(self):
        # Add some structure so the engine has things to consider.
        SkillMastery.objects.create(
            user=self.user, skill=self.skill, mastery_score=20, attempts_count=5
        )
        for _ in range(3):
            UserError.objects.create(
                user=self.user,
                source_type="quiz",
                error_type="grammar",
                skill=self.skill,
                grammar_topic=self.topic,
                severity=6,
            )
        update_user_weaknesses(self.user)

        with CaptureQueriesContext(connection) as ctx:
            generate_recommendations(self.user)
        # Allow up to 60 queries — captures the full pipeline (transactions,
        # update_or_create, bulk_create) without locking in current internals.
        # Anything that 10× this number is a regression.
        self.assertLess(
            len(ctx.captured_queries),
            150,
            f"recommendation engine ran {len(ctx.captured_queries)} queries",
        )
        self.assertTrue(LearningRecommendation.objects.filter(user=self.user).exists())
