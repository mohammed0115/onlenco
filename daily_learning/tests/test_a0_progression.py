"""A0 → A1 promotion service tests."""
from __future__ import annotations

import datetime

from django.test import TestCase
from django.utils import timezone

from daily_learning.services import a0_progression_service as ap
from daily_learning.services.daily_plan_generator import generate_for_user
from daily_learning.services.daily_progress_service import (
    complete_plan,
    mark_item_complete,
)

from .factories import make_student


def _seed_snapshot(user, *, days_back=0, lessons=0, questions=0, correct=0, vocab=0):
    from motivation.models import LearnerActivitySnapshot
    on_date = timezone.localdate() - datetime.timedelta(days=days_back)
    snap, _ = LearnerActivitySnapshot.objects.update_or_create(
        user=user, date=on_date,
        defaults={
            "lessons_completed": lessons,
            "questions_answered": questions,
            "correct_answers": correct,
            "vocabulary_words_learned": vocab,
        },
    )
    return snap


def _ensure_slp(user, *, level="A0"):
    """The test factory doesn't seed StudentLearningProfile — promotion
    tests need one to verify the level flip."""
    from learning_core.models import StudentLearningProfile
    slp, _ = StudentLearningProfile.objects.get_or_create(
        user=user, defaults={"current_cefr_level": level, "theta_score": -1.5},
    )
    return slp


class A0ProgressionMetricsTests(TestCase):
    def test_zero_state_reports_not_eligible(self):
        user = make_student(username="ap_zero", cefr_level="A0",
                            onboarding_path="beginner_start")
        snap = ap.check_a0_promotion_criteria(user)
        self.assertEqual(snap["current_level"], "A0")
        self.assertFalse(snap["eligible"])
        self.assertEqual(snap["lessons_completed"], 0)

    def test_partial_progress_still_not_eligible(self):
        user = make_student(username="ap_partial", cefr_level="A0",
                            onboarding_path="beginner_start")
        # Halfway on lessons + questions, but accuracy + vocab not met.
        _seed_snapshot(user, lessons=10, questions=50, correct=40, vocab=70)
        snap = ap.check_a0_promotion_criteria(user)
        self.assertFalse(snap["eligible"])

    def test_full_criteria_marks_eligible(self):
        user = make_student(username="ap_eligible", cefr_level="A0",
                            onboarding_path="beginner_start")
        _seed_snapshot(user, lessons=20, questions=100, correct=80, vocab=160)
        snap = ap.check_a0_promotion_criteria(user)
        self.assertTrue(snap["eligible"])
        self.assertGreaterEqual(snap["accuracy_pct"], 75.0)

    def test_low_accuracy_blocks_promotion(self):
        """100 questions, 60% accuracy → not eligible."""
        user = make_student(username="ap_lowacc", cefr_level="A0",
                            onboarding_path="beginner_start")
        _seed_snapshot(user, lessons=20, questions=100, correct=60, vocab=160)
        snap = ap.check_a0_promotion_criteria(user)
        self.assertFalse(snap["eligible"])
        self.assertEqual(snap["accuracy_pct"], 60.0)


class A0PromoteTests(TestCase):
    def test_promote_flips_profile_and_learning_profile(self):
        user = make_student(username="ap_flip", cefr_level="A0",
                            onboarding_path="beginner_start")
        _ensure_slp(user, level="A0")
        _seed_snapshot(user, lessons=20, questions=100, correct=85, vocab=160)
        promoted = ap.maybe_promote_a0_to_a1(user)
        self.assertTrue(promoted)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.cefr_level, "A1")
        from learning_core.models import StudentLearningProfile
        slp = StudentLearningProfile.objects.get(user=user)
        self.assertEqual(slp.current_cefr_level, "A1")

    def test_promote_idempotent_when_not_eligible(self):
        user = make_student(username="ap_no_change", cefr_level="A0",
                            onboarding_path="beginner_start")
        self.assertFalse(ap.maybe_promote_a0_to_a1(user))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.cefr_level, "A0")

    def test_promote_idempotent_after_first_flip(self):
        user = make_student(username="ap_idem", cefr_level="A0",
                            onboarding_path="beginner_start")
        _seed_snapshot(user, lessons=20, questions=100, correct=85, vocab=160)
        self.assertTrue(ap.maybe_promote_a0_to_a1(user))
        self.assertFalse(ap.maybe_promote_a0_to_a1(user),
                         "Second call must be a no-op")

    def test_complete_plan_triggers_promotion_when_eligible(self):
        """End-to-end: a learner who has already cleared the metric
        thresholds gets promoted the moment their next A0 plan is
        marked complete.

        Seed the metrics on YESTERDAY's snapshot so today's plan-completion
        flow (which fires `motivation_engine.run_for_user` and rebuilds
        today's snapshot from scratch) doesn't clobber the seeded totals.
        """
        user = make_student(username="ap_e2e", cefr_level="A0",
                            onboarding_path="beginner_start")
        _ensure_slp(user, level="A0")
        _seed_snapshot(user, days_back=1,
                       lessons=20, questions=100, correct=85, vocab=160)
        plan = generate_for_user(user)
        for item in plan.items.all():
            mark_item_complete(item)
        complete_plan(plan, force=True)
        user.profile.refresh_from_db()
        self.assertEqual(
            user.profile.cefr_level, "A1",
            "Completing an A0 plan with threshold metrics must promote.",
        )
