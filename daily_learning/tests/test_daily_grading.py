"""Prompt 18.3B — server-side Daily Quiz grading + listen_build_sentence."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from daily_learning.models import (
    DailyLearningItem, DailyLearningPlan, DailyLearningResult,
)
from daily_learning.services import (
    daily_grading, daily_listen_build, daily_progress_service,
)

User = get_user_model()


def _item(**kw):
    """Unsaved item for pure grading tests."""
    kw.setdefault("metadata", {})
    return DailyLearningItem(**kw)


class GradeItemTests(TestCase):
    # 1 — MCQ
    def test_mcq_correct_and_wrong(self):
        it = _item(item_type="quiz", correct_answer="am", options=["am", "is", "are"])
        self.assertTrue(daily_grading.grade_item(it, {"answer": "am"})["is_correct"])
        self.assertFalse(daily_grading.grade_item(it, {"answer": "is"})["is_correct"])

    def test_mcq_normalization(self):
        it = _item(item_type="quiz", correct_answer="I am.")
        for ans in ("i am", "  I AM ", "I am!"):
            self.assertTrue(daily_grading.grade_item(it, {"answer": ans})["is_correct"], ans)

    # 2 — shuffle safety (compare by text, not index/option order)
    def test_option_order_does_not_affect_grading(self):
        a = _item(item_type="quiz", correct_answer="are", options=["am", "is", "are"])
        b = _item(item_type="quiz", correct_answer="are", options=["are", "is", "am"])
        self.assertTrue(daily_grading.grade_item(a, {"answer": "are"})["is_correct"])
        self.assertTrue(daily_grading.grade_item(b, {"answer": "are"})["is_correct"])

    # 3 — word_order
    def test_word_order_tokens(self):
        it = _item(item_type="word_order", correct_answer="I am Ahmed")
        self.assertTrue(daily_grading.grade_item(it, {"tokens": ["I", "am", "Ahmed"]})["is_correct"])
        self.assertFalse(daily_grading.grade_item(it, {"tokens": ["am", "I", "Ahmed"]})["is_correct"])

    def test_word_order_raw_string_with_spaces(self):
        it = _item(item_type="word_order", correct_answer="I am Ahmed")
        self.assertTrue(daily_grading.grade_item(it, {"answer": "I   am  Ahmed"})["is_correct"])

    # 4 — listen_build (word_order + metadata.listen_build; no migration)
    def test_listen_build_grading(self):
        it = _item(item_type="word_order", correct_answer="I am a student",
                   metadata={"listen_build": True})
        good = daily_grading.grade_item(it, {"tokens": ["I", "am", "a", "student"]})
        self.assertTrue(good["is_correct"])
        self.assertEqual(good["question_type"], "listen_build_sentence")
        bad = daily_grading.grade_item(it, {"tokens": ["a", "student", "I", "am"]})
        self.assertFalse(bad["is_correct"])

    def test_non_gradable_item_is_not_scored(self):
        it = _item(item_type="motivation", correct_answer="")
        g = daily_grading.grade_item(it, {"answer": "anything"})
        self.assertFalse(g["gradable"])

    def test_builder_shape(self):
        d = daily_listen_build.build_listen_build_item(cefr_level="A1")
        self.assertEqual(d["item_type"], "word_order")
        self.assertTrue(d["metadata"]["listen_build"])
        self.assertEqual(d["cefr_level"], "A1")
        self.assertTrue(d["correct_answer"])


@override_settings(AXES_ENABLED=False)
class CompleteItemViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dq@x.com", password="pw")
        self.client.force_login(self.user)
        self.plan = DailyLearningPlan.objects.create(
            user=self.user, date=timezone.localdate(), cefr_level="A1",
        )

    def _item(self, **kw):
        kw.setdefault("daily_plan", self.plan)
        kw.setdefault("item_type", "quiz")
        return DailyLearningItem.objects.create(**kw)

    def _post(self, item, payload):
        return self.client.post(
            f"/daily/items/{item.id}/complete/",
            data=json.dumps(payload), content_type="application/json",
        )

    # 5 — server grades; stores metadata; ignores frontend correctness
    def test_server_grades_and_stores(self):
        it = self._item(correct_answer="am", options=["am", "is", "are"])
        r = self._post(it, {"answer": "am"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["is_correct"])
        it.refresh_from_db()
        self.assertTrue(it.metadata.get("is_correct"))
        self.assertTrue(it.is_completed)

    def test_does_not_trust_frontend_is_correct(self):
        it = self._item(correct_answer="am")
        r = self._post(it, {"answer": "WRONG", "is_correct": True})
        self.assertFalse(r.json()["is_correct"])   # server overrides
        it.refresh_from_db()
        self.assertFalse(it.metadata.get("is_correct"))

    def test_listen_build_via_view(self):
        it = self._item(item_type="word_order", correct_answer="I am a student",
                        metadata={"listen_build": True})
        self.assertTrue(self._post(it, {"tokens": ["I", "am", "a", "student"]}).json()["is_correct"])


class CompletePlanScoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dp@x.com", password="pw")
        self.plan = DailyLearningPlan.objects.create(
            user=self.user, date=timezone.localdate(), cefr_level="A1",
        )

    def _item(self, correct):
        it = DailyLearningItem.objects.create(
            daily_plan=self.plan, item_type="quiz", correct_answer="am",
        )
        daily_progress_service.mark_item_complete(
            it, user_answer="am" if correct else "no",
            grade={"is_correct": correct, "score": 1 if correct else 0, "gradable": True},
        )
        return it

    # 6 — score reflects correctness
    def test_score_is_correctness_based(self):
        self._item(True)
        self._item(False)
        res = daily_progress_service.complete_plan(self.plan, force=True)
        self.assertEqual(res.score, 50.0)   # 1 correct of 2 graded

    def test_legacy_plan_without_grades_uses_completion(self):
        # Old flow: items completed with no grade metadata → completion %.
        for _ in range(2):
            DailyLearningItem.objects.create(
                daily_plan=self.plan, item_type="vocabulary",
            )
        for it in self.plan.items.all():
            daily_progress_service.mark_item_complete(it)   # no grade
        res = daily_progress_service.complete_plan(self.plan, force=True)
        self.assertEqual(res.score, 100.0)   # completion fallback


@override_settings(AXES_ENABLED=False)
class TemplateAndIsolationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sec@x.com", password="pw")
        self.client.force_login(self.user)
        self.plan = DailyLearningPlan.objects.create(
            user=self.user, date=timezone.localdate(), cefr_level="A1",
            status="in_progress",
        )
        DailyLearningItem.objects.create(
            daily_plan=self.plan, item_type="quiz", question="Pick one",
            options=["a", "b", "c"], correct_answer="HIDDENANSWERZZ", order=0,
        )

    # 7 — no correct_answer leak in the rendered page
    def test_no_answer_leak_in_html(self):
        html = self.client.get("/daily/").content.decode()
        self.assertNotIn("data-quiz-target", html)
        self.assertNotIn("data-word-order-target", html)
        self.assertNotIn("data-writing-target", html)
        self.assertNotIn("HIDDENANSWERZZ", html)   # correct_answer never rendered

    # 9 — Daily Quiz never touches CourseLessonProgress
    def test_completing_daily_does_not_touch_course_progress(self):
        from courses.models import CourseLessonProgress
        before = CourseLessonProgress.objects.count()
        for it in self.plan.items.all():
            self.client.post(
                f"/daily/items/{it.id}/complete/",
                data=json.dumps({"answer": "a"}), content_type="application/json",
            )
        self.client.post("/daily/complete/", {"force": "1"})
        self.assertEqual(CourseLessonProgress.objects.count(), before)


class ListenBuildGenerationTests(TestCase):
    # 8 — opt-in generation injects an A1-appropriate listen_build item
    @override_settings(DAILY_LISTEN_BUILD_ENABLED=True)
    def test_a1_plan_includes_listen_build_when_enabled(self):
        from daily_learning.services import daily_plan_generator
        user = User.objects.create_user(username="lb@x.com", password="pw")
        prof = user.profile
        prof.cefr_level = "A1"
        prof.save()
        plan = daily_plan_generator.generate_for_user(user, force=True, allow_ai=False)
        lb = [i for i in plan.items.all() if (i.metadata or {}).get("listen_build")]
        self.assertGreaterEqual(len(lb), 1)
        self.assertEqual(lb[0].item_type, "word_order")
        self.assertIn(lb[0].cefr_level, ("A1",))
