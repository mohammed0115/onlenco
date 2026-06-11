"""Prompt 18.3C — CEFR coverage, listen_build policy, Weekly Review gate."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from daily_learning.services import daily_cefr, daily_plan_generator

User = get_user_model()


def _user(username, level=""):
    u = User.objects.create_user(username=username, password="pw")
    if level is not None:
        u.profile.cefr_level = level
        u.profile.save()
    return u


class CefrResolutionTests(TestCase):
    def test_beginner_resolves_a0(self):
        u = _user("a0@x.com", "A0")
        self.assertEqual(daily_cefr.resolve_daily_cefr_level(u), "A0")

    def test_placement_a1_resolves_a1(self):
        u = _user("a1@x.com", "A1")
        self.assertEqual(daily_cefr.resolve_daily_cefr_level(u), "A1")

    def test_missing_level_falls_back_to_a1(self):
        u = _user("none@x.com", "")
        self.assertEqual(daily_cefr.resolve_daily_cefr_level(u), "A1")

    def test_allowed_levels_are_same_or_lower(self):
        self.assertEqual(daily_cefr.allowed_daily_levels("A0"), ["A0"])
        self.assertEqual(daily_cefr.allowed_daily_levels("A2"), ["A0", "A1", "A2"])
        self.assertTrue(daily_cefr.is_level_allowed("A0", "A1"))
        self.assertFalse(daily_cefr.is_level_allowed("B1", "A1"))   # no level-up


class CefrCoverageTests(TestCase):
    def _gen(self, level):
        u = _user(f"gen-{level}@x.com", level)
        return daily_plan_generator.generate_for_user(u, force=True, allow_ai=False)

    def test_a0_plan_has_no_higher_level_items(self):
        plan = self._gen("A0")
        self.assertEqual(plan.cefr_level, "A0")
        for it in plan.items.all():
            self.assertTrue(daily_cefr.is_level_allowed(it.cefr_level, "A0"),
                            f"A0 plan leaked {it.cefr_level}")

    def test_a1_plan_has_no_b1_plus_items(self):
        plan = self._gen("A1")
        for it in plan.items.all():
            self.assertTrue(daily_cefr.is_level_allowed(it.cefr_level, "A1"),
                            f"A1 plan leaked {it.cefr_level}")

    def test_grading_engine_still_stable(self):
        # 18.3B sanity: server grading unchanged.
        from daily_learning.models import DailyLearningItem
        from daily_learning.services import daily_grading
        it = DailyLearningItem(item_type="quiz", correct_answer="am", metadata={})
        self.assertTrue(daily_grading.grade_item(it, {"answer": "AM "})["is_correct"])


class ListenBuildPolicyTests(TestCase):
    def _plan(self, level):
        u = _user(f"lb-{level}@x.com", level)
        return daily_plan_generator.generate_for_user(u, force=True, allow_ai=False)

    def _has_listen_build(self, plan):
        return any((i.metadata or {}).get("listen_build") for i in plan.items.all())

    def test_disabled_by_default_no_listen_build(self):
        self.assertFalse(self._has_listen_build(self._plan("A1")))

    @override_settings(DAILY_LISTEN_BUILD_ENABLED=True)
    def test_enabled_shows_for_a1(self):
        self.assertTrue(self._has_listen_build(self._plan("A1")))

    @override_settings(DAILY_LISTEN_BUILD_ENABLED=True)
    def test_never_shows_for_a0_even_when_enabled(self):
        plan = self._plan("A0")
        self.assertEqual(plan.cefr_level, "A0")
        self.assertFalse(self._has_listen_build(plan))   # A0 path forbids word_order


class WeeklyReviewGateTests(TestCase):
    def setUp(self):
        from courses.models import Course, CourseLevel, CourseUnit, Lesson
        self.user = _user("wk@x.com", "A0")
        level, _ = CourseLevel.objects.get_or_create(code="A0", defaults={"name": "A0", "order": 1})
        self.course = Course.objects.create(title="WK", slug="wk-course", level=level, status="published")
        self.unit = CourseUnit.objects.create(course=self.course, order=1, title="U1")
        self.lessons = [
            Lesson.objects.create(course=self.course, unit=self.unit, order=i,
                                  title=f"L{i}", status="published")
            for i in (1, 2, 3)
        ]

    def _complete(self, lesson):
        from courses.models import CourseLessonProgress
        CourseLessonProgress.objects.create(
            user=self.user, lesson=lesson, completed_at=timezone.now())

    def test_gate_false_before_three_lessons(self):
        from courses.services import weekly_review_gate
        self.assertFalse(weekly_review_gate.should_show_weekly_review(self.user, self.unit))
        self._complete(self.lessons[0])
        self.assertFalse(weekly_review_gate.should_show_weekly_review(self.user, self.unit))

    def test_gate_true_after_three_lessons(self):
        from courses.services import weekly_review_gate
        for le in self.lessons:
            self._complete(le)
        self.assertTrue(weekly_review_gate.should_show_weekly_review(self.user, self.unit))

    def test_gate_does_not_write_progress(self):
        from courses.models import CourseLessonProgress
        from courses.services import weekly_review_gate
        for le in self.lessons:
            self._complete(le)
        before = CourseLessonProgress.objects.count()
        weekly_review_gate.should_show_weekly_review(self.user, self.unit)
        weekly_review_gate.pending_weekly_reviews(self.user, self.course)
        self.assertEqual(CourseLessonProgress.objects.count(), before)   # read-only

    def test_pending_lists_completed_unit(self):
        from courses.services import weekly_review_gate
        for le in self.lessons:
            self._complete(le)
        pending = weekly_review_gate.pending_weekly_reviews(self.user, self.course)
        self.assertIn(self.unit, pending)
