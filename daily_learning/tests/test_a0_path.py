"""A0 plan generation tests.

The A0 path is hand-curated and never calls AI. These tests verify
the contract: A0 students get A0 content, with bilingual support,
no leaking technical keys, and the right item types.
"""
from __future__ import annotations

import datetime

from django.test import TestCase
from django.utils import timezone

from daily_learning.models import DailyLearningPlan
from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class A0PathTests(TestCase):
    def test_a0_student_gets_a0_plan(self):
        user = make_student(
            username="a0student",
            cefr_level="A0",
            language="ar",
            onboarding_path="beginner_start",
        )
        plan = generate_for_user(user, on_date=datetime.date(2026, 5, 12))
        self.assertEqual(plan.cefr_level, "A0")
        self.assertIn(plan.plan_type, {"beginner_start", "streak_recovery", "normal_daily_plan"})

    def test_a0_plan_contains_5_to_8_items(self):
        """Including the closing motivation item, the plan stays in range."""
        user = make_student(username="a0count", cefr_level="A0",
                            onboarding_path="beginner_start")
        plan = generate_for_user(user)
        count = plan.items.count()
        # A0 topic = 5 items + 1 motivation = 6 — well within 5..8.
        self.assertGreaterEqual(count, 5)
        self.assertLessEqual(count, 8)

    def test_a0_plan_includes_speaking_and_quiz(self):
        user = make_student(username="a0skills", cefr_level="A0",
                            onboarding_path="beginner_start")
        plan = generate_for_user(user)
        types = set(plan.items.values_list("item_type", flat=True))
        # A0 topic guarantees both — see a0_templates.A0_TOPICS.
        self.assertTrue({"speaking", "quiz"}.issubset(types))

    def test_a0_plan_includes_motivation(self):
        user = make_student(username="a0mot", cefr_level="A0",
                            onboarding_path="beginner_start")
        plan = generate_for_user(user)
        self.assertTrue(plan.items.filter(item_type="motivation").exists())
        self.assertTrue((plan.metadata or {}).get("motivation_message"))

    def test_a0_arabic_user_gets_arabic_content(self):
        user = make_student(username="a0ar", cefr_level="A0",
                            language="ar", onboarding_path="beginner_start")
        plan = generate_for_user(user)
        first_item = plan.items.order_by("order").first()
        # Arabic title contains Arabic characters
        self.assertRegex(first_item.title, r"[؀-ۿ]")

    def test_a0_english_user_gets_english_content(self):
        user = make_student(username="a0en", cefr_level="A0",
                            language="en", onboarding_path="beginner_start")
        plan = generate_for_user(user)
        first_item = plan.items.order_by("order").first()
        # Latin-only first character set (no Arabic in the title)
        self.assertNotRegex(first_item.title, r"[؀-ۿ]")

    def test_no_raw_technical_keys_in_a0_content(self):
        user = make_student(username="a0clean", cefr_level="A0",
                            onboarding_path="beginner_start")
        plan = generate_for_user(user)
        for item in plan.items.all():
            combined = " ".join([
                item.title or "", item.instructions or "",
                item.content_text or "", item.question or "",
            ])
            for banned in ("item_type", "underscore", "blank blank blank",
                           "{", "[null"):
                self.assertNotIn(banned, combined.lower(),
                                 f"banned token '{banned}' leaked into item {item.id}")

    def test_existing_plan_is_not_duplicated(self):
        user = make_student(username="a0dup", cefr_level="A0",
                            onboarding_path="beginner_start")
        on = datetime.date(2026, 5, 12)
        p1 = generate_for_user(user, on_date=on)
        p2 = generate_for_user(user, on_date=on)
        self.assertEqual(p1.id, p2.id)
        self.assertEqual(
            DailyLearningPlan.objects.filter(user=user, date=on).count(), 1
        )
