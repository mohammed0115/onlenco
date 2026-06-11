"""Prompt 18.3D — student-facing smoke: Daily Quiz UI + Weekly Review card."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from daily_learning.models import DailyLearningPlan
from daily_learning.services import daily_cefr

User = get_user_model()


def _student(username, level="A0"):
    u = User.objects.create_user(username=username, password="pw")
    u.profile.cefr_level = level
    u.profile.subscription_status = "active"
    u.profile.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
    u.profile.save()
    return u


@override_settings(AXES_ENABLED=False)
class DailyQuizUiSmokeTests(TestCase):
    def setUp(self):
        self.user = _student("dui@x.com", "A0")
        self.client.force_login(self.user)

    def _plan(self):
        return DailyLearningPlan.objects.get(user=self.user, date=timezone.localdate())

    def test_daily_page_opens_for_a0(self):
        self.assertEqual(self.client.get("/daily/").status_code, 200)

    def test_a0_page_has_no_grading_target_leak(self):
        html = self.client.get("/daily/").content.decode()
        self.assertNotIn("data-quiz-target", html)
        self.assertNotIn("data-word-order-target", html)
        self.assertNotIn("data-writing-target", html)

    def test_a0_plan_has_no_higher_level_items(self):
        self.client.get("/daily/")
        for it in self._plan().items.all():
            self.assertTrue(daily_cefr.is_level_allowed(it.cefr_level, "A0"))

    def test_complete_item_correct_and_wrong_from_ui(self):
        self.client.get("/daily/")
        # A0 plan's quiz item has options + a real correct_answer.
        item = self._plan().items.filter(item_type="quiz").first()
        self.assertIsNotNone(item)
        r_ok = self.client.post(
            f"/daily/items/{item.id}/complete/",
            data=json.dumps({"answer": item.correct_answer}),
            content_type="application/json")
        self.assertTrue(r_ok.json()["is_correct"])
        # A second, wrong-answer item.
        other = self._plan().items.filter(item_type="quiz").exclude(id=item.id).first()
        if other:
            r_bad = self.client.post(
                f"/daily/items/{other.id}/complete/",
                data=json.dumps({"answer": "definitely-wrong-zz"}),
                content_type="application/json")
            self.assertFalse(r_bad.json()["is_correct"])

    def test_completing_plan_stores_correctness_score(self):
        from daily_learning.services import daily_grading, daily_progress_service
        self.client.get("/daily/")
        plan = self._plan()
        quizzes = list(plan.items.filter(item_type="quiz")[:2])
        if len(quizzes) >= 2:
            daily_progress_service.mark_item_complete(
                quizzes[0], grade={"is_correct": True, "score": 1, "gradable": True})
            daily_progress_service.mark_item_complete(
                quizzes[1], grade={"is_correct": False, "score": 0, "gradable": True})
            res = daily_progress_service.complete_plan(plan, force=True)
            self.assertEqual(res.score, 50.0)


@override_settings(AXES_ENABLED=False)
class ListenBuildUiSmokeTests(TestCase):
    def _plan_for(self, level):
        u = _student(f"lbui-{level}@x.com", level)
        self.client.force_login(u)
        self.client.get("/daily/")
        return u, DailyLearningPlan.objects.get(user=u, date=timezone.localdate())

    @override_settings(DAILY_LISTEN_BUILD_ENABLED=True)
    def test_listen_build_renders_for_a1(self):
        u, plan = self._plan_for("A1")
        lb = next((i for i in plan.items.all() if (i.metadata or {}).get("listen_build")), None)
        self.assertIsNotNone(lb)
        html = self.client.get("/daily/").content.decode()
        self.assertIn('data-testid="listen-build-btn"', html)   # audio control rendered
        self.assertIn("data-word", html)             # scrambled word buttons
        self.assertNotIn("data-word-order-target", html)
        # Correct tokens grade True via the backend.
        r = self.client.post(
            f"/daily/items/{lb.id}/complete/",
            data=json.dumps({"tokens": lb.correct_answer.split()}),
            content_type="application/json")
        self.assertTrue(r.json()["is_correct"])
        r2 = self.client.post(
            f"/daily/items/{lb.id}/complete/",
            data=json.dumps({"tokens": list(reversed(lb.correct_answer.split()))}),
            content_type="application/json")
        # Already completed (idempotent) — but a fresh wrong grade on a new item
        # is covered in the grading tests; here just assert no crash.
        self.assertEqual(r2.status_code, 200)

    @override_settings(DAILY_LISTEN_BUILD_ENABLED=True)
    def test_a0_gets_no_listen_build_even_when_enabled(self):
        u, plan = self._plan_for("A0")
        self.assertFalse(any((i.metadata or {}).get("listen_build") for i in plan.items.all()))
        html = self.client.get("/daily/").content.decode()
        self.assertNotIn('data-testid="listen-build-btn"', html)   # button never rendered for A0


@override_settings(AXES_ENABLED=False)
class WeeklyReviewCardTests(TestCase):
    def setUp(self):
        from courses.models import Course, CourseLevel, CourseUnit, Lesson
        self.user = _student("wkui@x.com", "A1")
        self.client.force_login(self.user)
        level, _ = CourseLevel.objects.get_or_create(code="A1", defaults={"name": "A1", "order": 2})
        self.course = Course.objects.create(
            title="WK UI", slug="wk-ui", level=level, status="published", is_free=True)
        self.unit = CourseUnit.objects.create(course=self.course, order=1, title="U1")
        self.lessons = [
            Lesson.objects.create(course=self.course, unit=self.unit, order=i,
                                  title=f"L{i}", status="published")
            for i in (1, 2, 3)
        ]
        self.url = reverse("courses:course_detail", args=[self.course.pk])

    def _complete_all(self):
        from courses.models import CourseLessonProgress
        for le in self.lessons:
            CourseLessonProgress.objects.create(
                user=self.user, lesson=le, completed_at=timezone.now())

    def test_card_hidden_before_three_lessons(self):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("weekly-review-card", html)

    def test_card_visible_after_three_lessons(self):
        self._complete_all()
        html = self.client.get(self.url).content.decode()
        self.assertIn("weekly-review-card", html)

    def test_card_render_does_not_change_progress(self):
        from courses.models import CourseLessonProgress
        self._complete_all()
        before = CourseLessonProgress.objects.count()
        self.client.get(self.url)
        self.assertEqual(CourseLessonProgress.objects.count(), before)

    def test_course_detail_ok_with_no_pending(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("weekly-review-card", r.content.decode())


@override_settings(AXES_ENABLED=False)
class HeroCoverHardeningTests(TestCase):
    """Prompt 18.3E — course-detail hero cover must respect is_student_visible."""

    def setUp(self):
        from courses.models import Course, CourseLevel, CourseUnit, Lesson, LessonImagePrompt
        from django.core.files.base import ContentFile
        self.user = _student("hero@x.com", "A1")
        self.client.force_login(self.user)
        level, _ = CourseLevel.objects.get_or_create(code="A1", defaults={"name": "A1", "order": 2})
        self.course = Course.objects.create(
            title="Hero", slug="hero-c", level=level, status="published", is_free=True)
        unit = CourseUnit.objects.create(course=self.course, order=1, title="U1")
        first = Lesson.objects.create(
            course=self.course, unit=unit, order=1, title="L1", status="published")
        self.cover = LessonImagePrompt.objects.create(
            lesson=first, prompt_type="cover", prompt="x", sort_order=0)
        self.cover.generated_image.save("hero.png", ContentFile(b"img"), save=False)
        self.cover.is_generated = True
        self.cover.save()
        self.url = reverse("courses:course_detail", args=[self.course.pk])

    def test_pending_hero_cover_not_shown(self):
        self.cover.generation_status = "needs_review"
        self.cover.save(update_fields=["generation_status"])
        html = self.client.get(self.url).content.decode()
        self.assertNotIn(self.cover.generated_image.url, html)

    def test_approved_hero_cover_shown(self):
        self.cover.generation_status = "approved"
        self.cover.save(update_fields=["generation_status"])
        html = self.client.get(self.url).content.decode()
        self.assertIn(self.cover.generated_image.url, html)
