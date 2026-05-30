"""Phase 5 — XP / Hearts / Streak / Daily-goal / Badges / Encouragement.

Covers:
  * XP ledger idempotency + aggregates.
  * Hearts policy decrement / depletion / retry reset.
  * Streak state machine — start, same-day no-op, next-day +1, gap reset.
  * Daily goal — progress tracking, one-shot bonus, summary shape.
  * Badge catalog seed (idempotent) + Challenge-driven evaluation.
  * Encouragement service — bilingual lookups.
  * Challenge integration — completion fires streak + daily goal + badges.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from motivation.models import (
    BadgeDefinition, DailyGoal, DailyGoalProgress, StreakActivity,
    StudentStreak, UserBadge, UserXP, XPTransaction,
)
from motivation.services import (
    badge_catalog, daily_goal_service, encouragement_service,
    hearts_service, streak_v2, xp_ledger,
)


User = get_user_model()


def _make_user(name: str = "rewards-user") -> User:
    u = User.objects.create_user(
        username=name, password="pw", email=f"{name}@onlenco.test",
    )
    if hasattr(u, "profile"):
        u.profile.email_verified = True
        u.profile.subscription_status = "active"
        u.profile.save()
    return u


# ---------------------------------------------------------------------------
# 1. XP ledger
# ---------------------------------------------------------------------------

class XPLedgerTests(TestCase):
    def test_xp_transaction_created_for_correct_answer(self):
        u = _make_user("xp-1")
        tx = xp_ledger.award_xp(u, 10, source_type="challenge_answer",
                                source_id=42, reason="test")
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 10)
        self.assertEqual(tx.source_type, "challenge_answer")

    def test_xp_total_updates(self):
        u = _make_user("xp-2")
        xp_ledger.award_xp(u, 10, source_type="challenge_answer", source_id=1)
        xp_ledger.award_xp(u, 5,  source_type="challenge_answer", source_id=2)
        agg = UserXP.objects.get(user=u)
        self.assertEqual(agg.total_xp, 15)

    def test_xp_not_awarded_twice_for_same_answer(self):
        u = _make_user("xp-3")
        first = xp_ledger.award_xp(u, 10, source_type="challenge_answer", source_id=999)
        second = xp_ledger.award_xp(u, 10, source_type="challenge_answer", source_id=999)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(UserXP.objects.get(user=u).total_xp, 10)
        self.assertEqual(XPTransaction.objects.filter(user=u).count(), 1)

    def test_zero_amount_is_noop(self):
        u = _make_user("xp-4")
        self.assertIsNone(xp_ledger.award_xp(u, 0, source_type="challenge_answer", source_id=1))
        self.assertEqual(XPTransaction.objects.filter(user=u).count(), 0)

    def test_completion_bonus_awarded_once(self):
        from courses.services.challenge_rewards import credit_completion_bonus
        u = _make_user("xp-5")
        class _S: pk = 7; user = u; wrong_count = 0
        first = credit_completion_bonus(u, session=_S())
        second = credit_completion_bonus(u, session=_S())
        self.assertEqual(first, 20)
        self.assertEqual(second, 0)

    def test_perfect_bonus_awarded_once(self):
        from courses.services.challenge_rewards import credit_perfect_bonus
        u = _make_user("xp-6")
        class _S: pk = 8; user = u; wrong_count = 0
        first = credit_perfect_bonus(u, session=_S())
        second = credit_perfect_bonus(u, session=_S())
        self.assertEqual(first, 10)
        self.assertEqual(second, 0)

    def test_perfect_bonus_not_awarded_when_wrong_count(self):
        from courses.services.challenge_rewards import credit_perfect_bonus
        u = _make_user("xp-7")
        class _S: pk = 9; user = u; wrong_count = 2
        self.assertEqual(credit_perfect_bonus(u, session=_S()), 0)


# ---------------------------------------------------------------------------
# 2. Hearts policy
# ---------------------------------------------------------------------------

class HeartsPolicyTests(TestCase):
    def _session(self, **kw):
        # Lightweight fake session — implements just the surface
        # hearts_service touches.
        from types import SimpleNamespace
        defaults = dict(
            hearts_total=5, hearts_remaining=5,
            status="in_progress", is_active=True,
        )
        defaults.update(kw)
        s = SimpleNamespace(**defaults)
        s.save = lambda update_fields=None: None
        return s

    def test_get_default_hearts_returns_5(self):
        self.assertEqual(hearts_service.get_default_hearts(None), 5)

    def test_wrong_answer_removes_heart(self):
        s = self._session(hearts_remaining=5)
        ok = hearts_service.apply_wrong_answer(s)
        self.assertTrue(ok)
        self.assertEqual(s.hearts_remaining, 4)

    def test_hearts_zero_fails_session(self):
        s = self._session(hearts_remaining=1)
        hearts_service.apply_wrong_answer(s)
        self.assertFalse(hearts_service.can_continue(s))
        display = hearts_service.get_hearts_display(s)
        self.assertTrue(display["depleted"])

    def test_retry_resets_hearts(self):
        s = self._session(hearts_remaining=0)
        hearts_service.reset_hearts_for_retry(s)
        self.assertEqual(s.hearts_remaining, 5)


# ---------------------------------------------------------------------------
# 3. Streak system
# ---------------------------------------------------------------------------

class StreakTests(TestCase):
    def test_streak_starts_on_first_completed_challenge(self):
        u = _make_user("st-1")
        streak, advanced = streak_v2.record_learning_activity(
            u, "challenge_completed",
        )
        self.assertTrue(advanced)
        self.assertEqual(streak.current_streak, 1)
        self.assertEqual(streak.longest_streak, 1)

    def test_streak_does_not_increment_twice_same_day(self):
        u = _make_user("st-2")
        streak_v2.record_learning_activity(u, "challenge_completed")
        streak, advanced = streak_v2.record_learning_activity(
            u, "lesson_completed",
        )
        self.assertFalse(advanced)
        self.assertEqual(streak.current_streak, 1)

    def test_streak_increments_next_day(self):
        u = _make_user("st-3")
        today = timezone.localdate()
        streak_v2.record_learning_activity(
            u, "challenge_completed",
            on_date=today - timedelta(days=1),
        )
        streak, advanced = streak_v2.record_learning_activity(
            u, "challenge_completed", on_date=today,
        )
        self.assertTrue(advanced)
        self.assertEqual(streak.current_streak, 2)

    def test_streak_resets_after_gap(self):
        u = _make_user("st-4")
        today = timezone.localdate()
        streak_v2.record_learning_activity(
            u, "challenge_completed",
            on_date=today - timedelta(days=3),
        )
        streak, advanced = streak_v2.record_learning_activity(
            u, "challenge_completed", on_date=today,
        )
        self.assertTrue(advanced)
        self.assertEqual(streak.current_streak, 1)   # reset
        self.assertEqual(streak.longest_streak, 1)

    def test_longest_streak_updates(self):
        u = _make_user("st-5")
        today = timezone.localdate()
        for i in range(5):
            streak_v2.record_learning_activity(
                u, "challenge_completed",
                on_date=today - timedelta(days=4 - i),
            )
        streak = streak_v2.get_streak(u)
        self.assertEqual(streak.current_streak, 5)
        self.assertEqual(streak.longest_streak, 5)
        # Now break the streak with a gap, then restart.
        streak_v2.record_learning_activity(
            u, "challenge_completed",
            on_date=today + timedelta(days=10),
        )
        streak.refresh_from_db()
        self.assertEqual(streak.current_streak, 1)
        self.assertEqual(streak.longest_streak, 5)   # still 5

    def test_non_counting_activity_logged_but_no_advance(self):
        u = _make_user("st-6")
        streak, advanced = streak_v2.record_learning_activity(
            u, "challenge_started",
        )
        self.assertFalse(advanced)
        self.assertEqual(streak.current_streak, 0)
        self.assertEqual(StreakActivity.objects.filter(user=u).count(), 1)


# ---------------------------------------------------------------------------
# 4. Daily goal
# ---------------------------------------------------------------------------

class DailyGoalTests(TestCase):
    def test_daily_goal_progress_updates_with_xp(self):
        u = _make_user("dg-1")
        progress, completed, bonus = daily_goal_service.update_daily_goal_progress(u, 20)
        self.assertEqual(progress.xp_earned, 20)
        self.assertFalse(progress.completed)
        self.assertFalse(completed)
        self.assertEqual(bonus, 0)

    def test_daily_goal_completed_when_target_crossed(self):
        u = _make_user("dg-2")
        daily_goal_service.update_daily_goal_progress(u, 30)
        progress, just_completed, bonus = daily_goal_service.update_daily_goal_progress(u, 30)
        self.assertTrue(progress.completed)
        self.assertTrue(just_completed)
        self.assertEqual(bonus, 25)

    def test_daily_goal_bonus_awarded_once(self):
        u = _make_user("dg-3")
        daily_goal_service.update_daily_goal_progress(u, 60)   # crosses 50
        # Adding more XP today must NOT re-award the bonus.
        progress, just_completed, bonus = daily_goal_service.update_daily_goal_progress(u, 30)
        self.assertFalse(just_completed)
        self.assertEqual(bonus, 0)
        # Only ONE daily_goal_bonus XP transaction.
        self.assertEqual(
            XPTransaction.objects.filter(user=u, source_type="daily_goal_bonus").count(),
            1,
        )

    def test_daily_goal_summary(self):
        u = _make_user("dg-4")
        daily_goal_service.update_daily_goal_progress(u, 30)
        summary = daily_goal_service.get_daily_goal_summary(u)
        self.assertEqual(summary["target"], 50)
        self.assertEqual(summary["earned"], 30)
        self.assertEqual(summary["pct"], 60)
        self.assertFalse(summary["completed"])

    def test_daily_goal_records_streak_activity(self):
        u = _make_user("dg-5")
        daily_goal_service.update_daily_goal_progress(u, 60)
        self.assertTrue(
            StreakActivity.objects.filter(
                user=u, activity_type="daily_goal_completed",
            ).exists()
        )


# ---------------------------------------------------------------------------
# 5. Badge catalog
# ---------------------------------------------------------------------------

class BadgeCatalogTests(TestCase):
    def test_seed_badge_definitions_idempotent(self):
        c1, u1 = badge_catalog.seed_default_badges()
        c2, u2 = badge_catalog.seed_default_badges()
        self.assertEqual(c1, 10)
        self.assertEqual(c2, 0)        # no new rows
        self.assertEqual(u2, 10)       # all upserted
        self.assertEqual(BadgeDefinition.objects.count(), 10)

    def test_award_badge_creates_userbadge_and_credits_xp(self):
        badge_catalog.seed_default_badges()
        u = _make_user("badge-1")
        b, was_new = badge_catalog.award_badge(u, "FIRST_LESSON")
        self.assertTrue(was_new)
        self.assertIsNotNone(b)
        self.assertEqual(UserXP.objects.get(user=u).total_xp, 50)

    def test_badge_not_awarded_twice(self):
        badge_catalog.seed_default_badges()
        u = _make_user("badge-2")
        badge_catalog.award_badge(u, "FIRST_LESSON")
        b, was_new = badge_catalog.award_badge(u, "FIRST_LESSON")
        self.assertFalse(was_new)
        # Only one xp_reward grant in the ledger.
        self.assertEqual(
            XPTransaction.objects.filter(
                user=u, source_type="badge_reward", source_id="FIRST_LESSON",
            ).count(),
            1,
        )

    def test_award_unknown_badge_is_safe(self):
        u = _make_user("badge-3")
        b, was_new = badge_catalog.award_badge(u, "TOTALLY_FAKE_BADGE")
        self.assertIsNone(b)
        self.assertFalse(was_new)


# ---------------------------------------------------------------------------
# 6. Encouragement service
# ---------------------------------------------------------------------------

class EncouragementTests(TestCase):
    def test_correct_answer_returns_english_default(self):
        msg = encouragement_service.get_message("correct_answer", "en", {"k": 1})
        self.assertTrue(msg)
        self.assertIn(msg, [pair[0] for pair in encouragement_service.MESSAGES["correct_answer"]])

    def test_arabic_branch_returns_arabic(self):
        msg = encouragement_service.get_message("wrong_answer", "ar", {"k": 1})
        self.assertTrue(msg)
        self.assertIn(msg, [pair[1] for pair in encouragement_service.MESSAGES["wrong_answer"]])

    def test_bilingual_returns_both(self):
        en, ar = encouragement_service.get_bilingual("perfect_challenge", {"x": 1})
        self.assertEqual(en, "Perfect! You answered everything correctly.")
        self.assertEqual(ar, "ممتاز! أجبت على كل شيء بشكل صحيح.")

    def test_unknown_event_returns_empty(self):
        self.assertEqual(encouragement_service.get_message("no_such_event"), "")


# ---------------------------------------------------------------------------
# 7. Challenge integration
# ---------------------------------------------------------------------------

class ChallengeIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from courses.models import (
            Course, CourseLevel, CourseUnit, Lesson, LessonQuestion, LessonQuiz,
        )
        level, _ = CourseLevel.objects.get_or_create(
            code="C0", defaults={"name": "Phase5 tests", "order": 99},
        )
        teacher = _make_user("teacher-int")
        cls.course = Course.objects.create(
            title="Phase5 int", slug="ph5-int", level=level,
            teacher=teacher, created_by=teacher,
            status="published", is_active=True,
        )
        cls.unit = CourseUnit.objects.create(course=cls.course, title="U1", order=1)
        cls.lesson = Lesson.objects.create(
            course=cls.course, unit=cls.unit, title="L1", order=1,
            status="published", is_active=True,
        )
        cls.quiz = LessonQuiz.objects.create(lesson=cls.lesson, title="Q")
        for i in range(3):
            LessonQuestion.objects.create(
                quiz=cls.quiz, order=i + 1,
                question_type="multiple_choice",
                question_text=f"Pick the greeting #{i + 1}",
                options=["Hello", "Banana"],
                correct_answer="Hello",
            )
        cls.student = _make_user("int-student")
        from courses.models import CourseEnrollment
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)
        # Seed badges so evaluation has rows to work with.
        badge_catalog.seed_default_badges()

    def _run_session_to_completion(self, *, perfect=True):
        from courses.services import challenge_runner
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        for qid in list(session.question_ids):
            from courses.models import LessonQuestion
            q = LessonQuestion.objects.get(pk=qid)
            ans = "Hello" if perfect else "Banana"   # Hello = correct
            challenge_runner.submit_answer(session, q, ans)
            session.refresh_from_db()
            if not session.is_active:
                break
            challenge_runner.continue_to_next(session)
            session.refresh_from_db()
        return session

    def test_challenge_completion_credits_xp_ledger(self):
        session = self._run_session_to_completion(perfect=True)
        self.assertEqual(session.status, "completed")
        # Each correct answer + completion + perfect = 3 source types.
        tx_count = XPTransaction.objects.filter(user=self.student).count()
        self.assertGreaterEqual(tx_count, 3)
        # Completion bonus exists exactly once.
        self.assertEqual(
            XPTransaction.objects.filter(
                user=self.student, source_type="challenge_completion",
            ).count(),
            1,
        )
        # Perfect bonus exists exactly once.
        self.assertEqual(
            XPTransaction.objects.filter(
                user=self.student, source_type="perfect_bonus",
            ).count(),
            1,
        )

    def test_challenge_completion_updates_streak(self):
        self._run_session_to_completion(perfect=True)
        streak = streak_v2.get_streak(self.student)
        self.assertEqual(streak.current_streak, 1)
        self.assertTrue(
            StreakActivity.objects.filter(
                user=self.student, activity_type="challenge_completed",
            ).exists()
        )

    def test_challenge_completion_updates_daily_goal(self):
        self._run_session_to_completion(perfect=True)
        progress = DailyGoalProgress.objects.get(
            user=self.student, date=timezone.localdate(),
        )
        # Correct answers (3 × 10) + completion 20 + perfect 10 = 60 XP.
        self.assertGreaterEqual(progress.xp_earned, 50)
        self.assertTrue(progress.completed)

    def test_challenge_failed_does_not_increment_streak(self):
        # Force the session to fail by submitting wrong answers until
        # hearts deplete.
        from courses.services import challenge_runner
        from courses.models import LessonQuestion
        # Crank up question count so wrong-answer count >= hearts (5).
        for j in range(5):
            LessonQuestion.objects.create(
                quiz=self.quiz, order=10 + j,
                question_type="multiple_choice",
                question_text=f"Extra #{j}",
                options=["Hello", "Banana"], correct_answer="Hello",
            )
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        for qid in list(session.question_ids):
            q = LessonQuestion.objects.get(pk=qid)
            try:
                challenge_runner.submit_answer(session, q, "Banana")
            except challenge_runner.ChallengeError:
                break
            session.refresh_from_db()
            if not session.is_active:
                break
            try:
                challenge_runner.continue_to_next(session)
            except challenge_runner.ChallengeError:
                break
        self.assertEqual(session.status, "failed")
        self.assertFalse(
            StreakActivity.objects.filter(
                user=self.student, activity_type="challenge_completed",
            ).exists()
        )

    def test_perfect_challenge_awards_perfect_badge(self):
        self._run_session_to_completion(perfect=True)
        self.assertTrue(
            UserBadge.objects.filter(
                user=self.student, badge_code="PERFECT_CHALLENGE",
            ).exists()
        )

    def test_first_completed_challenge_awards_first_badge(self):
        self._run_session_to_completion(perfect=True)
        self.assertTrue(
            UserBadge.objects.filter(
                user=self.student, badge_code="FIRST_CHALLENGE",
            ).exists()
        )

    def test_completion_idempotent_on_repeat_terminate(self):
        """Calling _on_session_terminate twice for the SAME session must
        NOT double-credit completion bonus."""
        session = self._run_session_to_completion(perfect=True)
        completion_count_before = XPTransaction.objects.filter(
            user=self.student, source_type="challenge_completion",
        ).count()
        from courses.services.challenge_runner import _on_session_terminate
        _on_session_terminate(session, perfect=True)
        completion_count_after = XPTransaction.objects.filter(
            user=self.student, source_type="challenge_completion",
        ).count()
        self.assertEqual(completion_count_before, completion_count_after)


# ---------------------------------------------------------------------------
# 8. Summary screen surfaces rewards (light integration)
# ---------------------------------------------------------------------------

class SummaryRewardsRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from courses.models import (
            ChallengeSession, Course, CourseEnrollment, CourseLevel, CourseUnit,
            Lesson, LessonQuestion, LessonQuiz,
        )
        level, _ = CourseLevel.objects.get_or_create(
            code="C0", defaults={"name": "Phase5 ui", "order": 99},
        )
        teacher = _make_user("teacher-sum")
        cls.course = Course.objects.create(
            title="Phase5 sum", slug="ph5-sum", level=level,
            teacher=teacher, created_by=teacher,
            status="published", is_active=True,
        )
        cls.unit = CourseUnit.objects.create(course=cls.course, title="U", order=1)
        cls.lesson = Lesson.objects.create(
            course=cls.course, unit=cls.unit, title="L", order=1,
            status="published", is_active=True,
        )
        cls.quiz = LessonQuiz.objects.create(lesson=cls.lesson, title="Q")
        LessonQuestion.objects.create(
            quiz=cls.quiz, order=1,
            question_type="multiple_choice",
            question_text="x", options=["Hello"], correct_answer="Hello",
        )
        cls.student = _make_user("sum-student")
        CourseEnrollment.objects.get_or_create(user=cls.student, course=cls.course)
        # Seed and run a session so the rewards context is populated.
        badge_catalog.seed_default_badges()

    def _login(self):
        from django.test import Client
        c = Client(SERVER_NAME="127.0.0.1")
        c.force_login(self.student)
        if hasattr(self.student, "profile"):
            self.student.profile.preferred_language = "en"
            self.student.profile.save()
        return c

    def test_summary_includes_xp_breakdown_and_streak(self):
        from courses.services import challenge_runner
        from django.urls import reverse
        from courses.models import LessonQuestion
        session = challenge_runner.start_or_resume(self.student, self.lesson)
        q = LessonQuestion.objects.get(pk=session.question_ids[0])
        challenge_runner.submit_answer(session, q, "Hello")
        challenge_runner.continue_to_next(session)
        session.refresh_from_db()
        c = self._login()
        r = c.get(reverse("courses:challenge_summary",
                          args=[self.course.pk, self.lesson.pk, session.pk]),
                  HTTP_HOST="127.0.0.1")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("data-xp-breakdown", body)
        self.assertIn("data-streak", body)
        self.assertIn("data-daily-goal", body)
        self.assertIn("data-encouragement", body)
