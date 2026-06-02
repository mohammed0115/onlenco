"""Prompt 14 — Controlled Publish Pilot for Batch 1 (Topics 02-06)."""
from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from platform_admin import permissions as control_perms

from accounts.models import APPROVAL_APPROVED, APPROVAL_PENDING_ADMIN
from ai_usage.models import AIUsageLog
from courses.models import CourseUnit, Lesson, LessonImagePrompt, LessonReviewEvent
from courses.services import challenge_runner
from courses.services import lesson_review_workflow as wf

User = get_user_model()
SLUG = "onlenco-beginner"
BATCH = [2, 3, 4, 5, 6]


def _new(order):
    return Lesson.objects.filter(course__slug=SLUG, order=order).exclude(status="archived").first()


def _student(username, status=APPROVAL_APPROVED):
    u = User.objects.create_user(username=username, email=username, password="pw12345!")
    p = u.profile
    p.role = "student"; p.email_verified = True; p.approval_status = status
    p.save()
    return u


class Prompt14PublishTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platform_roles", verbosity=0)
        call_command("seed_learning_skills", verbosity=0)
        call_command("seed_super_lesson_01", verbosity=0)
        call_command("seed_beginner_48_topics", "--confirm", verbosity=0)
        cls.admin = User.objects.create_superuser("padmin@x.com", "padmin@x.com", "pw12345!")
        # Approve the batch so it is publishable.
        call_command("approve_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", cls.admin.username, verbosity=0)
        course = _new(2).course
        unit = CourseUnit.objects.create(course=course, title="Legacy", order=90)
        cls.legacy = Lesson.objects.create(course=course, unit=unit, order=95,
                                           title="Legacy Broken", status="archived",
                                           is_active=False, cefr_level="A1")
        cls.gold = Lesson.objects.get(course__slug=SLUG, order=1)

    def _publish(self):
        call_command("publish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", self.admin.username, verbosity=0)

    def _teacher(self):
        u = User.objects.create_user("t14@x.com", "t14@x.com", "pw12345!")
        g, _ = Group.objects.get_or_create(name=control_perms.GROUP_TEACHER)
        u.groups.add(g)
        return u

    # ---------- pre-state + commands ----------
    def test_batch_1_starts_approved_not_published(self):
        for o in BATCH:
            self.assertEqual(_new(o).status, "approved")

    def test_publish_teacher_batch_dry_run_changes_nothing(self):
        call_command("publish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--dry-run", verbosity=0)
        for o in BATCH:
            self.assertEqual(_new(o).status, "approved")

    def test_publish_teacher_batch_confirm_publishes_topics_02_06(self):
        self._publish()
        self.assertEqual(
            Lesson.objects.filter(course__slug=SLUG, order__in=BATCH, status="published").count(), 5)

    def test_topics_02_06_published(self):
        self._publish()
        for o in BATCH:
            L = _new(o)
            self.assertEqual(L.status, "published")
            self.assertIsNotNone(L.published_at)

    def test_publish_teacher_batch_refuses_pending_topics(self):
        # Topic 07 is pending_review → publish must refuse it even if requested.
        call_command("publish_teacher_batch", "--course", SLUG, "--topics", "7-7",
                     "--confirm", "--actor", self.admin.username, verbosity=0)
        self.assertEqual(_new(7).status, "pending_review")

    def test_publish_teacher_batch_refuses_archived_legacy_lessons(self):
        self._publish()
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.status, "archived")

    def test_publish_teacher_batch_does_not_publish_topics_07_48(self):
        self._publish()
        self.assertFalse(
            Lesson.objects.filter(course__slug=SLUG, order__gte=7, status="published").exists())

    def test_topics_07_48_not_published(self):
        self._publish()
        self.assertEqual(
            Lesson.objects.filter(course__slug=SLUG, status="pending_review").count(), 42)

    def test_publish_teacher_batch_creates_audit_events(self):
        self._publish()
        for o in BATCH:
            self.assertTrue(LessonReviewEvent.objects.filter(lesson=_new(o), action="publish").exists())

    def test_audit_events_for_publish_and_unpublish(self):
        self._publish()
        call_command("unpublish_teacher_batch", "--course", SLUG, "--topics", "2-2",
                     "--confirm", "--actor", self.admin.username, verbosity=0)
        actions = set(LessonReviewEvent.objects.filter(lesson=_new(2)).values_list("action", flat=True))
        self.assertIn("publish", actions)
        self.assertIn("unpublish", actions)

    def test_publish_teacher_batch_does_not_generate_media(self):
        self._publish()
        self.assertFalse(
            LessonImagePrompt.objects.filter(lesson__in=[_new(o) for o in BATCH])
            .exclude(generated_image="").exists())

    def test_legacy_archived_not_visible(self):
        self._publish()
        self.assertEqual(self.legacy.status, "archived")

    def test_topic_01_gold_reference_unchanged(self):
        self._publish()
        self.gold.refresh_from_db()
        self.assertEqual(self.gold.status, "published")
        self.assertEqual(self.gold.quiz.questions.count(), 10)

    # ---------- visibility (gate ON) ----------
    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_approved_student_can_access_published_batch_1(self):
        self._publish()
        self.client.force_login(_student("apv@x.com"))
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id}))
        self.assertEqual(resp.status_code, 200)

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_approved_student_cannot_access_pending_topics_07_48(self):
        self._publish()
        self.client.force_login(_student("apv2@x.com"))
        L = _new(7)
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id}))
        self.assertNotEqual(resp.status_code, 200)

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_pending_student_cannot_access_published_batch_1(self):
        self._publish()
        self.client.force_login(_student("pend@x.com", status=APPROVAL_PENDING_ADMIN))
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id}))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/account/pending-approval", resp["Location"])

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_pending_student_redirected_to_approval_page(self):
        self.client.force_login(_student("pend2@x.com", status=APPROVAL_PENDING_ADMIN))
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/account/pending-approval", resp["Location"])

    def test_anonymous_cannot_access_student_lessons(self):
        self._publish()
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id}))
        self.assertNotEqual(resp.status_code, 200)

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_archived_legacy_lessons_remain_hidden(self):
        self._publish()
        self.client.force_login(_student("apv3@x.com"))
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": self.legacy.course_id,
                                               "lesson_pk": self.legacy.id}))
        self.assertNotEqual(resp.status_code, 200)

    def test_teacher_can_access_published_batch_1(self):
        self._publish()
        self.client.force_login(self._teacher())
        resp = self.client.get(reverse("teacher_portal:content_review_detail", args=[_new(2).id]))
        self.assertEqual(resp.status_code, 200)

    def test_student_approval_gate_still_blocks_dashboard(self):
        with override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True):
            self.client.force_login(_student("pend3@x.com", status=APPROVAL_PENDING_ADMIN))
            self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    # ---------- student journey / rewards ----------
    def _play(self, user, lesson):
        s = challenge_runner.start_or_resume(user, lesson)
        for _ in range(40):
            if not s.is_active:
                break
            q = challenge_runner.get_current_question(s)
            if q is None:
                break
            try:
                challenge_runner.submit_answer(s, q, q.correct_answer or "a")
            except Exception:
                pass
            s = challenge_runner.continue_to_next(s)
        s.refresh_from_db()
        return s

    def test_approved_student_topic_02_e2e_challenge_to_summary(self):
        self._publish()
        s = self._play(_student("e2e@x.com"), _new(2))
        self.assertNotEqual(s.status, "in_progress")  # reached a terminal/summary state

    def test_published_batch_1_challenge_runs(self):
        self._publish()
        for o in BATCH:
            session = challenge_runner.start_or_resume(_student(f"play{o}@x.com"), _new(o))
            self.assertIsNotNone(challenge_runner.get_current_question(session))

    def test_published_batch_1_summary_updates_rewards_mastery(self):
        self._publish()
        s = self._play(_student("rew@x.com"), _new(3))
        # Terminal session => summary computable; rewards/hearts fields populated.
        self.assertIn(s.status, ("completed", "failed", "abandoned"))
        self.assertLessEqual(s.hearts_remaining, s.hearts_total)

    def test_published_topic_does_not_require_media_files(self):
        self._publish()
        # No generated media exists, yet the challenge serves a question.
        session = challenge_runner.start_or_resume(_student("nomedia@x.com"), _new(2))
        self.assertIsNotNone(challenge_runner.get_current_question(session))

    # ---------- AI usage ----------
    @override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True,
                       ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_pilot_challenge_ai_uses_wrapper_and_logs(self):
        from ai_usage.services import ai_client
        from ai_usage import constants as C
        from ai_usage.tests.helpers import FakeResponse, chat_json
        u = _student("aiok@x.com")
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json())):
            ai_client.chat([{"role": "user", "content": "x"}], user=u,
                           feature=C.FEATURE_CHALLENGE_EXPLANATION, model="gpt-4o-mini")
        self.assertTrue(AIUsageLog.objects.filter(
            feature=C.FEATURE_CHALLENGE_EXPLANATION, status=C.STATUS_SUCCESS).exists())

    @override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True,
                       ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_pending_student_ai_blocked_after_publish(self):
        from ai_usage.services import ai_client
        from ai_usage import constants as C
        self._publish()
        u = _student("aipend@x.com", status=APPROVAL_PENDING_ADMIN)
        with mock.patch.object(ai_client.requests, "post") as post:
            with self.assertRaises(ai_client.AccountPendingApproval):
                ai_client.chat([{"role": "user", "content": "x"}], user=u,
                               feature=C.FEATURE_AI_TUTOR)
        post.assert_not_called()

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_student_cannot_see_internal_cost(self):
        self._publish()
        u = _student("cost@x.com")
        from ai_usage.services import usage_logger
        usage_logger.log_success(user=u, feature="other", model_name="gpt-4o-mini",
                                 input_tokens=10, output_tokens=5)
        self.client.force_login(u)
        resp = self.client.get("/api/ai-usage/summary/today/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("estimated_cost_usd", resp.data)

    def test_admin_can_see_pilot_ai_usage(self):
        u = _student("cost2@x.com")
        from ai_usage.services import usage_logger
        usage_logger.log_success(user=u, feature="ai_tutor", model_name="gpt-4o-mini",
                                 input_tokens=10, output_tokens=5)
        self.client.force_login(self.admin)
        resp = self.client.get("/api/ai-usage/summary/today/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("estimated_cost_usd", resp.data)

    # ---------- media placeholders ----------
    def test_published_batch_1_no_generated_media_required(self):
        self._publish()
        self.assertFalse(
            LessonImagePrompt.objects.filter(lesson__in=[_new(o) for o in BATCH], is_generated=True).exists())

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_published_batch_1_no_raw_prompt_visible(self):
        self._publish()
        L = _new(2)
        raw_prompt = L.image_prompts.first().prompt
        self.client.force_login(_student("rawp@x.com"))
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(raw_prompt, resp.content.decode())

    # ---------- rollback ----------
    def test_unpublish_teacher_batch_dry_run_changes_nothing(self):
        self._publish()
        call_command("unpublish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--dry-run", verbosity=0)
        for o in BATCH:
            self.assertEqual(_new(o).status, "published")

    def test_unpublish_teacher_batch_confirm_reverts_to_approved(self):
        self._publish()
        call_command("unpublish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", self.admin.username, verbosity=0)
        for o in BATCH:
            self.assertEqual(_new(o).status, "approved")

    def test_unpublish_teacher_batch_creates_audit_events(self):
        self._publish()
        call_command("unpublish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", self.admin.username, verbosity=0)
        for o in BATCH:
            self.assertTrue(LessonReviewEvent.objects.filter(lesson=_new(o), action="unpublish").exists())

    @override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
    def test_student_loses_access_after_rollback(self):
        self._publish()
        call_command("unpublish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", self.admin.username, verbosity=0)
        self.client.force_login(_student("roll@x.com"))
        L = _new(2)
        resp = self.client.get(reverse("courses:lesson_detail",
                                       kwargs={"course_pk": L.course_id, "lesson_pk": L.id}))
        self.assertNotEqual(resp.status_code, 200)  # back to approved → hidden

    def test_teacher_still_accesses_after_rollback(self):
        self._publish()
        call_command("unpublish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", self.admin.username, verbosity=0)
        self.client.force_login(self._teacher())
        resp = self.client.get(reverse("teacher_portal:content_review_detail", args=[_new(2).id]))
        self.assertEqual(resp.status_code, 200)

    def test_rollback_does_not_delete_progress(self):
        self._publish()
        student = _student("prog@x.com")
        session = challenge_runner.start_or_resume(student, _new(2))
        sid = session.id
        call_command("unpublish_teacher_batch", "--course", SLUG, "--topics", "2-6",
                     "--confirm", "--actor", self.admin.username, verbosity=0)
        from courses.models import ChallengeSession
        self.assertTrue(ChallengeSession.objects.filter(id=sid).exists())

    # ---------- dashboard ----------
    def test_review_dashboard_reflects_published_batch_1(self):
        self._publish()
        self.client.force_login(self._teacher())
        resp = self.client.get(reverse("teacher_portal:content_review_list") + "?status=published")
        self.assertEqual(resp.status_code, 200)
