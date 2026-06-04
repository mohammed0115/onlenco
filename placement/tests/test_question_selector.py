"""Selector service: stratified random pick from the bank."""
import random
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from placement.models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementQuestion,
)
from placement.services.placement_question_selector import (
    create_placement_attempt,
    select_speaking_questions,
    select_written_questions,
)

User = get_user_model()


class SelectorTests(TestCase):
    """Diverse fixture bank so the selector's stratification / variety /
    difficulty logic is exercised (independent of the curated seed)."""

    @classmethod
    def setUpTestData(cls):
        for topic in ["intro", "grammar_fix", "sentence", "daily", "reason"]:
            for j in range(4):
                PlacementQuestion.objects.create(
                    code=f"w.{topic}.{j}", question_text=f"Written {topic} {j}",
                    question_type="written", skill="grammar", topic=topic,
                    difficulty_score=0.2 + 0.2 * j, expected_answer_type="sentence",
                    is_active=True,
                )
        for topic in ["name", "age_country", "work_study", "hobby", "reason"]:
            for j in range(4):
                PlacementQuestion.objects.create(
                    code=f"s.{topic}.{j}", question_text=f"Speaking {topic} {j}",
                    question_type="speaking", skill="speaking", topic=topic,
                    difficulty_score=0.2 + 0.2 * j, expected_answer_type="voice",
                    is_active=True,
                )

    def setUp(self):
        self.user = User.objects.create_user(username="sel@x.com", password="pw")

    def test_create_attempt_picks_exactly_5_written_and_5_speaking(self):
        attempt = create_placement_attempt(self.user)
        self.assertEqual(
            attempt.questions.filter(section="written").count(), 5,
        )
        self.assertEqual(
            attempt.questions.filter(section="speaking").count(), 5,
        )

    def test_select_written_returns_5_active_only(self):
        chosen = select_written_questions(self.user, count=5,
                                          rng=random.Random(42))
        self.assertEqual(len(chosen), 5)
        self.assertTrue(all(q.is_active and q.question_type == "written"
                            for q in chosen))

    def test_select_speaking_returns_5_active_only(self):
        chosen = select_speaking_questions(self.user, count=5,
                                           rng=random.Random(7))
        self.assertEqual(len(chosen), 5)
        self.assertTrue(all(q.is_active and q.question_type == "speaking"
                            for q in chosen))

    def test_inactive_questions_excluded(self):
        PlacementQuestion.objects.filter(question_type="written").update(is_active=False)
        # Reactivate just enough to hit 5.
        keep = list(PlacementQuestion.objects.filter(question_type="written")[:5].values_list("id", flat=True))
        PlacementQuestion.objects.filter(id__in=keep).update(is_active=True)
        chosen = select_written_questions(self.user, count=5,
                                          rng=random.Random(0))
        self.assertEqual(len(chosen), 5)
        self.assertTrue(all(q.is_active for q in chosen))

    def test_selection_covers_multiple_topics(self):
        # With 5 buckets and 5 picks, each bucket should contribute one
        # question (topic uniqueness across picks is the spec rule).
        chosen = select_written_questions(self.user, count=5,
                                          rng=random.Random(123))
        topics = {q.topic for q in chosen}
        self.assertGreaterEqual(len(topics), 4,
                                f"expected variety, got topics={topics}")

    def test_two_attempts_differ(self):
        # 5 from a 100+ pool: probability that two random picks fully
        # overlap is vanishingly small. We use independent RNG seeds to
        # exercise the randomisation path.
        a = create_placement_attempt(self.user, rng=random.Random(1))
        b = create_placement_attempt(self.user, rng=random.Random(99))
        ids_a = set(a.questions.values_list("question_id", flat=True))
        ids_b = set(b.questions.values_list("question_id", flat=True))
        self.assertNotEqual(ids_a, ids_b)

    def test_attempt_persists_question_ids_for_refresh_stability(self):
        attempt = create_placement_attempt(self.user)
        first_ids = list(
            attempt.questions.order_by("section", "order").values_list("question_id", flat=True)
        )
        # Simulating a "refresh": the view re-fetches by attempt_id and
        # gets the SAME PlacementAttemptQuestion rows.
        refetched = list(
            PlacementAttemptQuestion.objects.filter(attempt=attempt)
            .order_by("section", "order").values_list("question_id", flat=True)
        )
        self.assertEqual(first_ids, refetched)

    def test_a0_beginner_path_never_sees_hard_questions(self):
        """A learner who chose beginner_start (or whose profile is A0)
        must never be handed a question above the A0 ceiling (0.45)."""
        self.user.profile.onboarding_path = "beginner_start"
        self.user.profile.cefr_level = "A0"
        self.user.profile.save(update_fields=["onboarding_path", "cefr_level"])
        attempt = create_placement_attempt(self.user)
        difficulties = list(
            attempt.questions.values_list("question__difficulty_score", flat=True)
        )
        self.assertTrue(difficulties, "attempt must produce some questions")
        self.assertTrue(
            all(d <= 0.45 for d in difficulties),
            f"A0 placement leaked difficulty>0.45: {sorted(difficulties)}",
        )

    def test_a1_user_sees_capped_but_higher_questions(self):
        """A1 ceiling is 0.55 — A2 grammar OK, B1 subjunctive not."""
        self.user.profile.cefr_level = "A1"
        self.user.profile.save(update_fields=["cefr_level"])
        attempt = create_placement_attempt(self.user)
        difficulties = list(
            attempt.questions.values_list("question__difficulty_score", flat=True)
        )
        self.assertTrue(all(d <= 0.55 for d in difficulties))

    def test_unknown_level_user_can_still_see_hard_questions(self):
        """No level signal means we keep the full-range probe so the
        test can actually discover the learner's ceiling."""
        # Default: profile.cefr_level blank, onboarding_path blank.
        attempt = create_placement_attempt(self.user)
        difficulties = list(
            attempt.questions.values_list("question__difficulty_score", flat=True)
        )
        # The selector aims for at least one hard (>=0.65) when ceiling
        # is unset and the bank can supply it.
        self.assertTrue(
            max(difficulties) >= 0.65,
            f"unknown-level user should still see at least one hard question; "
            f"got max={max(difficulties)}",
        )

    def test_selection_avoids_recently_used_questions(self):
        # Run two attempts back-to-back. With 100+ active questions and 5
        # picks, the selector should prefer unseen questions on the second
        # attempt.
        a = create_placement_attempt(self.user)
        b = create_placement_attempt(self.user)
        a_ids = set(a.questions.filter(section="written").values_list("question_id", flat=True))
        b_ids = set(b.questions.filter(section="written").values_list("question_id", flat=True))
        # Spec rule: avoid repeating questions if the bank can supply
        # alternatives. With 25 written-intro, 30 grammar, etc. the
        # second attempt should pick all-new questions.
        self.assertEqual(len(a_ids & b_ids), 0,
                         "second attempt should not repeat questions when the bank allows")
