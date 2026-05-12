"""A0 sequential progression tests.

The contract: a brand-new A0 learner MUST start at Unit 1 ("Hello,
my name is …") on day 1. They progress to the next topic only after
completing the previous one. The earlier hash-based picker could
land them on Unit 4 ("I like English") on day 1 — that's the bug
this suite locks against.
"""
from __future__ import annotations

import datetime

from django.test import TestCase
from django.utils import timezone

from daily_learning.models import DailyLearningPlan
from daily_learning.services import a0_templates
from daily_learning.services.daily_plan_generator import generate_for_user
from daily_learning.services.daily_progress_service import (
    complete_plan,
    mark_item_complete,
)

from .factories import make_student


class A0SequentialProgressionTests(TestCase):
    def test_day_one_lands_on_unit_1(self):
        """A brand-new A0 learner (no completed plans yet) must see
        the very first topic in the catalog — Unit 1, Hello."""
        user = make_student(
            username="seq_day1", cefr_level="A0",
            onboarding_path="beginner_start",
        )
        plan = generate_for_user(user, on_date=datetime.date(2026, 5, 12))
        self.assertEqual(plan.cefr_level, "A0")
        self.assertEqual(plan.metadata.get("topic_unit"), 1,
                         "Day 1 must be Unit 1 (Hello English)")
        # The first catalog topic is u1_hello.
        self.assertEqual(plan.metadata.get("topic_slug"),
                         a0_templates.A0_TOPICS[0].slug)

    def test_completion_advances_to_next_topic(self):
        """Completing today's plan must move the learner to the NEXT
        topic in the catalog on the following day."""
        user = make_student(
            username="seq_advance", cefr_level="A0",
            onboarding_path="beginner_start",
        )
        # Generate, complete, then jump to tomorrow.
        day1 = datetime.date(2026, 5, 12)
        plan_1 = generate_for_user(user, on_date=day1)
        for it in plan_1.items.all():
            mark_item_complete(it)
        complete_plan(plan_1, force=True)

        # Day 2 — should be the second topic in the catalog.
        plan_2 = generate_for_user(user, on_date=day1 + datetime.timedelta(days=1))
        self.assertEqual(plan_2.metadata.get("topic_slug"),
                         a0_templates.A0_TOPICS[1].slug,
                         "Day 2 should be the second catalog topic")

    def test_incomplete_plan_does_not_advance(self):
        """If yesterday's plan was never finished, the learner stays
        on the same topic — they need to finish before moving on."""
        user = make_student(
            username="seq_stay", cefr_level="A0",
            onboarding_path="beginner_start",
        )
        day1 = datetime.date(2026, 5, 12)
        plan_1 = generate_for_user(user, on_date=day1)
        first_slug = plan_1.metadata.get("topic_slug")
        # Don't complete plan_1 — let it sit pending.
        plan_2 = generate_for_user(user, on_date=day1 + datetime.timedelta(days=1))
        self.assertEqual(plan_2.metadata.get("topic_slug"), first_slug,
                         "Without completion, day 2 must repeat the topic")

    def test_each_user_starts_at_unit_1_independently(self):
        """A second A0 user signing up later still starts at Unit 1,
        regardless of when other users are."""
        user_a = make_student(
            username="seq_a", cefr_level="A0",
            onboarding_path="beginner_start",
        )
        user_b = make_student(
            username="seq_b", cefr_level="A0",
            onboarding_path="beginner_start",
        )
        plan_a = generate_for_user(user_a, on_date=datetime.date(2026, 5, 12))
        plan_b = generate_for_user(user_b, on_date=datetime.date(2026, 5, 20))
        self.assertEqual(plan_a.metadata.get("topic_slug"),
                         a0_templates.A0_TOPICS[0].slug)
        self.assertEqual(plan_b.metadata.get("topic_slug"),
                         a0_templates.A0_TOPICS[0].slug)


class A0StaleShapeRegenerationTests(TestCase):
    def test_stale_plan_with_writing_or_word_order_is_regenerated(self):
        """A pre-existing A0 plan that still uses the legacy 8-item
        shape (writing + word_order) must be auto-regenerated, not
        served stale."""
        user = make_student(
            username="stale_8", cefr_level="A0",
            onboarding_path="beginner_start",
        )
        # Hand-craft a plan resembling the legacy 8-item shape.
        from daily_learning.models import DailyLearningItem
        on = datetime.date(2026, 5, 12)
        legacy = DailyLearningPlan.objects.create(
            user=user, date=on, cefr_level="A0",
            plan_type="beginner_start",
            title="Legacy day", description="from old template",
        )
        DailyLearningItem.objects.create(
            daily_plan=legacy, item_type="vocabulary",
            title="v", order=0,
        )
        DailyLearningItem.objects.create(
            daily_plan=legacy, item_type="writing",   # legacy
            title="w", order=1,
        )
        legacy_id = legacy.id

        fresh = generate_for_user(user, on_date=on)
        # The stale plan should have been deleted and replaced with
        # the 6-item current spec.
        self.assertNotEqual(fresh.id, legacy_id,
                            "Stale plan must be replaced, not reused")
        types = set(fresh.items.values_list("item_type", flat=True))
        self.assertNotIn("writing", types)
        self.assertNotIn("word_order", types)
        self.assertEqual(fresh.items.count(), 6)
