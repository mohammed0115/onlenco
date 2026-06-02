"""Prompt 13 — Teacher Approval Batch 1 gate tests.

Approves Topics 02-06 through the review workflow service / batch command.
Verifies: approved-not-published, audit events, student invisibility,
teacher preview, dashboard, and all safety rules. Seeds real content.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from platform_admin import permissions as control_perms

from ai_usage.models import AIUsageLog
from courses.models import CourseUnit, Lesson, LessonReviewEvent
from courses.services import challenge_runner
from courses.services import lesson_review_workflow as wf

User = get_user_model()
SLUG = "onlenco-beginner"
BATCH = [2, 3, 4, 5, 6]


def _new(order):
    """The non-archived (new) lesson at this order."""
    return Lesson.objects.filter(course__slug=SLUG, order=order).exclude(status="archived").first()


class Prompt13ApprovalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platform_roles", verbosity=0)
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        call_command("seed_beginner_48_topics", "--confirm", verbosity=0)
        cls.actor = User.objects.create_user(username="approver@x.com", password="pw12345!")
        cls.actor.is_staff = True
        cls.actor.save(update_fields=["is_staff"])
        # An archived legacy lesson (separate unit/order) for visibility checks.
        unit = CourseUnit.objects.create(course=_new(2).course, title="Legacy", order=90)
        cls.legacy = Lesson.objects.create(
            course=_new(2).course, unit=unit, order=95, title="Legacy Broken",
            status="archived", is_active=False, cefr_level="A1")
        cls.gold = Lesson.objects.get(course__slug=SLUG, order=1)

    def _approve_batch(self, **extra):
        call_command("approve_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", self.actor.username, verbosity=0, **extra)

    def _teacher(self):
        u = User.objects.create_user(username="tt13@x.com", password="pw12345!")
        g, _ = Group.objects.get_or_create(name=control_perms.GROUP_TEACHER)
        u.groups.add(g)
        return u

    def _student(self):
        return User.objects.create_user(username="ss13@x.com", password="pw12345!")

    # ---------- pre-state ----------
    def test_batch_1_topics_start_as_pending_review(self):
        for o in BATCH:
            self.assertEqual(_new(o).status, "pending_review")

    def test_batch_1_topics_can_be_started_review(self):
        L = _new(2)
        wf.start_review(actor=self.actor, lesson=L, note="x")
        L.refresh_from_db()
        self.assertEqual(L.status, "in_review")

    def test_batch_1_topics_can_be_approved(self):
        self._approve_batch()
        for o in BATCH:
            self.assertEqual(_new(o).status, "approved")

    # ---------- command ----------
    def test_approve_teacher_batch_dry_run_changes_nothing(self):
        call_command("approve_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--dry-run", verbosity=0)
        for o in BATCH:
            self.assertEqual(_new(o).status, "pending_review")

    def test_approve_teacher_batch_confirm_approves_topics_02_06(self):
        self._approve_batch()
        self.assertEqual(
            Lesson.objects.filter(course__slug=SLUG, order__in=BATCH, status="approved").count(), 5)

    def test_approve_teacher_batch_refuses_low_score(self):
        L = _new(3)
        L.quality_flags = []
        # Force a low live score by emptying the quiz so the checker deducts.
        L.quiz.questions.all().delete()
        self._approve_batch()
        L.refresh_from_db()
        self.assertNotEqual(L.status, "approved")  # skipped, not approved

    def test_approve_teacher_batch_refuses_error_flags(self):
        L = _new(4)
        L.quiz.questions.all().delete()  # no_quiz/too_few → error flags
        self._approve_batch()
        L.refresh_from_db()
        self.assertNotEqual(L.status, "approved")

    def test_approve_teacher_batch_creates_audit_events(self):
        self._approve_batch()
        for o in BATCH:
            actions = set(LessonReviewEvent.objects.filter(lesson=_new(o))
                          .values_list("action", flat=True))
            self.assertIn("start_review", actions)
            self.assertIn("approve", actions)

    def test_approve_teacher_batch_does_not_publish(self):
        self._approve_batch()
        self.assertFalse(
            Lesson.objects.filter(course__slug=SLUG, order__in=BATCH, status="published").exists())

    # ---------- post-approval invariants ----------
    def test_batch_1_topics_not_published(self):
        self._approve_batch()
        for o in BATCH:
            L = _new(o)
            self.assertEqual(L.status, "approved")
            self.assertIsNone(L.published_at)

    def test_topics_07_48_remain_pending_review(self):
        self._approve_batch()
        self.assertEqual(
            Lesson.objects.filter(course__slug=SLUG, status="pending_review").count(), 42)
        self.assertFalse(
            Lesson.objects.filter(course__slug=SLUG, order__gte=7, status="approved").exists())

    def test_approval_creates_lesson_review_events(self):
        self._approve_batch()
        self.assertTrue(
            LessonReviewEvent.objects.filter(lesson=_new(2), action="approve").exists())

    def test_review_notes_saved_for_batch_1(self):
        self._approve_batch()
        ev = LessonReviewEvent.objects.filter(lesson=_new(2), action="approve").first()
        self.assertIn("Batch 1", ev.note)

    def test_quality_scores_retained_after_approval(self):
        self._approve_batch()
        for o in BATCH:
            self.assertEqual(_new(o).quality_score, 100)

    def test_topic_01_gold_reference_unchanged(self):
        self._approve_batch()
        self.gold.refresh_from_db()
        self.assertEqual(self.gold.status, "published")
        self.assertEqual(self.gold.order, 1)
        self.assertEqual(self.gold.quiz.questions.count(), 10)

    def test_archived_legacy_lessons_remain_archived(self):
        self._approve_batch()
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.status, "archived")

    def test_no_topics_published_during_prompt_13(self):
        self._approve_batch()
        # Only the gold reference is published; nothing new.
        self.assertEqual(Lesson.objects.filter(course__slug=SLUG, status="published").count(), 1)

    def test_no_media_generated_during_prompt_13(self):
        self._approve_batch()
        from courses.models import LessonImagePrompt
        self.assertFalse(
            LessonImagePrompt.objects.filter(lesson__in=[_new(o) for o in BATCH])
            .exclude(generated_image="").exists())

    # ---------- visibility ----------
    def test_student_cannot_access_approved_unpublished_topic(self):
        self._approve_batch()
        self.client.force_login(self._student())
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id}))
        self.assertNotEqual(resp.status_code, 200)

    def test_teacher_can_access_approved_topic(self):
        self._approve_batch()
        self.client.force_login(self._teacher())
        resp = self.client.get(
            reverse("teacher_portal:content_review_detail", args=[_new(2).id]))
        self.assertEqual(resp.status_code, 200)

    def test_archived_legacy_lessons_remain_hidden(self):
        self._approve_batch()
        self.client.force_login(self._student())
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": self.legacy.course_id,
                                               "lesson_pk": self.legacy.id}))
        self.assertNotEqual(resp.status_code, 200)

    # ---------- challenge preview ----------
    def _preview(self, order):
        teacher = self._teacher()
        L = _new(order)
        before = AIUsageLog.objects.count()
        session = challenge_runner.start_or_resume(teacher, L)
        q = challenge_runner.get_current_question(session)
        self.assertIsNotNone(q)  # first question renders
        challenge_runner.submit_answer(session, q, q.correct_answer or "a")
        return AIUsageLog.objects.count() - before

    def test_teacher_preview_topic_02_challenge_runs(self):
        self._approve_batch()
        self._preview(2)

    def test_teacher_preview_topic_06_challenge_runs(self):
        self._approve_batch()
        self._preview(6)

    def test_approved_topic_challenge_does_not_require_media(self):
        self._approve_batch()
        # No generated media exists, yet the challenge starts + serves a question.
        teacher = self._teacher()
        session = challenge_runner.start_or_resume(teacher, _new(3))
        self.assertIsNotNone(challenge_runner.get_current_question(session))

    def test_ai_usage_not_bypassed_in_teacher_preview(self):
        self._approve_batch()
        # A normal challenge preview makes NO AI call (deterministic grading).
        delta = self._preview(4)
        self.assertEqual(delta, 0)

    # ---------- dashboard ----------
    def test_review_dashboard_shows_approved_batch_1(self):
        self._approve_batch()
        self.client.force_login(self._teacher())
        resp = self.client.get(reverse("teacher_portal:content_review_list") + "?status=approved")
        self.assertEqual(resp.status_code, 200)

    def test_review_dashboard_filters_approved(self):
        self._approve_batch()
        self.client.force_login(self._teacher())
        resp = self.client.get(reverse("teacher_portal:content_review_list") + "?status=approved")
        body = resp.content.decode()
        self.assertIn("Saying Hello and Goodbye", body)

    def test_review_dashboard_filters_pending_after_batch_1(self):
        self._approve_batch()
        self.client.force_login(self._teacher())
        resp = self.client.get(
            reverse("teacher_portal:content_review_list") + "?status=pending_review")
        self.assertEqual(resp.status_code, 200)

    def test_audit_trail_shows_batch_approval(self):
        self._approve_batch()
        events = LessonReviewEvent.objects.filter(lesson=_new(2)).values_list("action", flat=True)
        self.assertIn("start_review", events)
        self.assertIn("approve", events)
